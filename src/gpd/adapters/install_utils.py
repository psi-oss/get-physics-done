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
from pathlib import Path

from gpd.adapters.tool_names import CONTEXTUAL_TOOL_REFERENCE_NAMES, reference_translation_map

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PATCHES_DIR_NAME = "gpd-local-patches"
MANIFEST_NAME = "gpd-file-manifest.json"
MAX_INCLUDE_EXPANSION_DEPTH = 10

# Subdirectories of specs/ that make up the installed get-physics-done/ content.
# Shared by all adapters.
GPD_CONTENT_DIRS = ("references", "templates", "workflows")

# Hook script filenames by purpose.
HOOK_SCRIPTS: dict[str, str] = {
    "statusline": "statusline.py",
    "check_update": "check_update.py",
    "codex_notify": "codex_notify.py",
    "runtime_detect": "runtime_detect.py",
}

# Legacy GPD hook basenames from older installs. Stored without extension so
# cleanup can remove stale files regardless of their historical suffix.
LEGACY_HOOK_BASENAMES = {
    "gpd-statusline",
    "gpd-check-update",
    "gpd-codex-notify",
    "statusline",
    "gpd-intel-index",
    "gpd-intel-session",
    "gpd-intel-prune",
}

# Orphaned files from previous GPD versions (relative to config dir)
_ORPHANED_FILES = [
    "hooks/gpd-notify.sh",  # Removed in v1.6.x
]

# Orphaned hook command patterns to remove from settings
_ORPHANED_HOOK_PATTERNS = [
    "gpd-notify.sh",  # Removed in v1.6.x
    "gpd-statusline",
    "gpd-check-update",
    "gpd-codex-notify",
    "gpd-intel-index",
    "gpd-intel-session",
    "gpd-intel-prune",
]

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


def replace_placeholders(content: str, path_prefix: str) -> str:
    """Replace GPD path placeholders in file content.

    Replaces ``{GPD_INSTALL_DIR}``, ``{GPD_AGENTS_DIR}``, and ``~/.claude/``
    references with *path_prefix*-based paths.

    The source spec files always use ``~/.claude/`` as a canonical placeholder
    for the runtime config directory, regardless of the target runtime.  This
    function rewrites that placeholder to *path_prefix*, which is the
    runtime-specific config path (e.g. ``~/.gemini/``, ``~/.codex/``,
    ``~/.config/opencode/``, or ``~/.claude/`` itself for Claude Code).

    Used by all adapters during install to rewrite .md file references.
    """
    content = content.replace("{GPD_INSTALL_DIR}", path_prefix + "get-physics-done")
    content = content.replace("{GPD_AGENTS_DIR}", path_prefix + "agents")
    content = re.sub(r"~/\.claude/", path_prefix, content)
    return content


def get_opencode_global_dir() -> str:
    """Resolve OpenCode global config directory following XDG spec.

    Priority: ``OPENCODE_CONFIG_DIR`` > ``dirname(OPENCODE_CONFIG)`` >
    ``XDG_CONFIG_HOME/opencode`` > ``~/.config/opencode``.
    """
    env_dir = os.environ.get("OPENCODE_CONFIG_DIR")
    if env_dir:
        return expand_tilde(env_dir) or env_dir

    env_cfg = os.environ.get("OPENCODE_CONFIG")
    if env_cfg:
        expanded = expand_tilde(env_cfg) or env_cfg
        return str(Path(expanded).parent)

    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return str(Path(expand_tilde(xdg) or xdg) / "opencode")

    return str(Path.home() / ".config" / "opencode")


def get_codex_global_dir() -> str:
    """Resolve Codex global config directory.

    Priority: ``CODEX_CONFIG_DIR`` > ``~/.codex``.
    """
    env_dir = os.environ.get("CODEX_CONFIG_DIR")
    if env_dir:
        return expand_tilde(env_dir) or env_dir
    return str(Path.home() / ".codex")


def get_codex_skills_dir() -> str:
    """Resolve Codex global skills directory.

    Priority: ``CODEX_SKILLS_DIR`` > ``~/.agents/skills``.
    """
    env_dir = os.environ.get("CODEX_SKILLS_DIR")
    if env_dir:
        return expand_tilde(env_dir) or env_dir
    return str(Path.home() / ".agents" / "skills")


def get_global_dir(runtime: str, explicit_dir: str | None = None) -> str:
    """Resolve the global config directory for *runtime*.

    *explicit_dir* takes highest priority (from ``--config-dir`` flag).
    Then runtime-specific env vars, then defaults.
    """
    if runtime == "opencode":
        if explicit_dir:
            return expand_tilde(explicit_dir) or explicit_dir
        return get_opencode_global_dir()

    if runtime == "codex":
        if explicit_dir:
            return expand_tilde(explicit_dir) or explicit_dir
        return get_codex_global_dir()

    if runtime == "gemini":
        if explicit_dir:
            return expand_tilde(explicit_dir) or explicit_dir
        env_dir = os.environ.get("GEMINI_CONFIG_DIR")
        if env_dir:
            return expand_tilde(env_dir) or env_dir
        return str(Path.home() / ".gemini")

    # Claude Code
    if explicit_dir:
        return expand_tilde(explicit_dir) or explicit_dir
    env_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if env_dir:
        return expand_tilde(env_dir) or env_dir
    return str(Path.home() / ".claude")


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
        raise PermissionError(f"Cannot write settings file: {p} — check directory permissions") from exc
    tmp_path.rename(p)


# ---------------------------------------------------------------------------
# Attribution helpers
# ---------------------------------------------------------------------------


def get_commit_attribution(
    runtime: str,
    *,
    explicit_config_dir: str | None = None,
) -> str | None:
    """Get commit attribution setting for *runtime*.

    Returns:
        ``None`` — remove Co-Authored-By lines.
        ``""`` (empty string) — keep default (no change).
        A non-empty string — replace attribution with this value.

    We use *empty string* to mean "keep default" since Python has no
    ``undefined`` sentinel.
    """
    if runtime == "opencode":
        config_path = Path(get_global_dir("opencode", explicit_config_dir)) / "opencode.json"
        config = read_settings(config_path)
        if config.get("disable_ai_attribution") is True:
            return None
        return ""

    if runtime == "codex":
        # Codex uses config.toml — default to keep
        return ""

    # Claude Code & Gemini share the same settings.json approach
    settings_path = Path(get_global_dir(runtime, explicit_config_dir)) / "settings.json"
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
            content = re.sub(r"\b" + escaped + r"\b", target, content)
            continue

        # Backtick-quoted
        content = content.replace(f"`{source_name}`", f"`{target}`")
        # "the X tool"
        content = re.sub(
            r"\b(the\s+)" + escaped + r"(\s+tool)",
            r"\g<1>" + target + r"\2",
            content,
            flags=re.IGNORECASE,
        )
        # "X tool" after punctuation/start-of-line
        content = re.sub(
            r"(^|[.,:;!?\-\s])" + escaped + r"(\s+tool\b)",
            r"\1" + target + r"\2",
            content,
            flags=re.MULTILINE,
        )
        # "Use X" / "using X" / "via X"
        content = re.sub(
            r"(\b(?:[Uu]se|[Uu]sing|[Vv]ia)\s+)" + escaped + r"\b",
            r"\1" + target,
            content,
        )
        # Function-style invocation, e.g. Task(...) or shell(...)
        content = re.sub(
            r"\b" + escaped + r"(?=\s*\()",
            target,
            content,
        )

    return content


def _translate_markdown_for_runtime(content: str, path_prefix: str, runtime: str) -> str:
    """Translate shared markdown content from canonical source form to *runtime*.

    This is used for markdown copied into installed shared content directories
    such as ``get-physics-done/workflows/`` and ``references/``. Those files are
    read directly by installed commands and agents, so command syntax, tool
    references, placeholders, and lightweight formatting need the same
    runtime-specific adaptation as primary prompts.
    """
    runtime_key = "claude-code" if runtime == "claude" else runtime
    content = replace_placeholders(content, path_prefix)

    if runtime_key == "codex":
        content = content.replace("/gpd:", "$gpd-")
    elif runtime_key == "opencode":
        content = content.replace("/gpd:", "/gpd-")

    if runtime_key == "gemini":
        content = strip_sub_tags(content)

    return convert_tool_references_in_body(content, reference_translation_map(runtime_key))


def expand_at_includes(
    content: str,
    src_root: str | Path,
    path_prefix: str,
    *,
    depth: int = 0,
    include_stack: set[str] | None = None,
) -> str:
    """Expand ``@path/to/file`` include directives by inlining referenced file content.

    Claude Code resolves these at runtime, but Gemini and Codex do not.
    This resolves includes at install time for runtimes that lack native resolution.

    Args:
        content: File content potentially containing ``@`` include lines.
        src_root: Source root directory (repo's ``get-physics-done/`` dir).
        path_prefix: Runtime-specific path prefix replacing ``~/.claude/``.
        depth: Current recursion depth (for cycle protection).
        include_stack: Set of already-included absolute paths (cycle detection).

    Examples::

        >>> expand_at_includes("no includes here", "/src", "~/.claude/")
        'no includes here'
        >>> expand_at_includes("@.gpd/notes.md", "/src", "~/.claude/")
        '@.gpd/notes.md'
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

        # Must start with @ followed by a path (not a BibTeX entry like @article{)
        if not trimmed.startswith("@") or len(trimmed) < 3 or trimmed[1] == " " or re.match(r"^@\w+\{", trimmed):
            result.append(line)
            continue

        # Extract the include path
        include_path = trimmed[1:]
        include_path = include_path.split(" (see")[0]  # strip "(see ..." suffixes
        include_path = include_path.split(" -> ")[0]  # strip "-> Section Name" suffixes
        include_path = include_path.strip()

        # Only treat paths that contain "/" (avoid false positives like decorators)
        if "/" not in include_path:
            result.append(line)
            continue

        # .gpd/ relative paths — project-specific, skip
        if include_path.startswith(".gpd/"):
            result.append(line)
            continue

        # Example paths — not real files
        if include_path.startswith("path/"):
            result.append(line)
            continue

        # Resolve against source directory
        src_path: Path | None = None
        if "get-physics-done/" in include_path:
            gpd_idx = include_path.index("get-physics-done/")
            relative_path = include_path[gpd_idx:]
            src_path = src_root.parent / relative_path
        elif "/agents/" in include_path:
            agents_idx = include_path.index("/agents/")
            relative_path = include_path[agents_idx + 1 :]
            src_path = src_root.parent / relative_path

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
            if body.startswith("---"):
                end_idx = body.index("---", 3) if "---" in body[3:] else -1
                if end_idx != -1:
                    actual_end = body.index("---", 3) + 3
                    body = body[actual_end:].strip()

            # Normalize path references in included content before recursion
            body = replace_placeholders(body, path_prefix)
            body = expand_at_includes(
                body,
                str(src_root),
                path_prefix,
                depth=depth + 1,
                include_stack=include_stack,
            )

            result.append("")
            result.append(f"<!-- [included: {src_path.name}] -->")
            result.append(body)
            result.append("<!-- [end included] -->")
            result.append("")
            include_stack.discard(abs_key)
        else:
            result.append(f"<!-- @ include not resolved: {include_path} -->")

    return "\n".join(result)


# ---------------------------------------------------------------------------
# Safe copy with path replacement
# ---------------------------------------------------------------------------


def copy_with_path_replacement(
    src_dir: str | Path,
    dest_dir: str | Path,
    path_prefix: str,
    runtime: str,
) -> None:
    """Safely copy *src_dir* to *dest_dir* with path replacement in ``.md`` files.

    Uses a copy-to-temp-then-swap strategy to prevent data loss if copy
    fails partway through. Symlinks in the source tree are skipped.

    Examples::

        >>> copy_with_path_replacement("src/", "dest/", "/custom/", "claude")
        # Copies src/ → dest/ with ~/.claude/ replaced by /custom/ in .md files

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
        _copy_dir_contents(src_dir, tmp_dir, path_prefix, runtime)

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
            _copy_dir_contents(entry, dest, path_prefix, runtime)
        elif entry.suffix == ".md":
            content = entry.read_text(encoding="utf-8")
            content = _translate_markdown_for_runtime(content, path_prefix, runtime)
            dest.write_text(content, encoding="utf-8")
        else:
            # Binary copy
            import shutil

            shutil.copy2(str(entry), str(dest))


# ---------------------------------------------------------------------------
# Cleanup helpers
# ---------------------------------------------------------------------------


def cleanup_orphaned_files(config_dir: str | Path) -> list[str]:
    """Remove orphaned files from previous GPD versions.

    Returns a list of relative paths that were removed.
    """
    config_dir = Path(config_dir)
    removed: list[str] = []

    for rel_path in _ORPHANED_FILES:
        full_path = config_dir / rel_path
        if full_path.exists():
            full_path.unlink()
            removed.append(rel_path)

    return removed


def cleanup_orphaned_hooks(settings: dict[str, object]) -> dict[str, object]:
    """Remove orphaned hook registrations from *settings*.

    Mutates and returns *settings* with orphaned GPD hooks removed.
    """
    hooks = settings.get("hooks")
    if isinstance(hooks, dict):
        for event_type, hook_entries in list(hooks.items()):
            if not isinstance(hook_entries, list):
                continue
            filtered = []
            for entry in hook_entries:
                entry_hooks = entry.get("hooks") if isinstance(entry, dict) else None
                if isinstance(entry_hooks, list):
                    has_orphaned = False
                    for h in entry_hooks:
                        cmd = h.get("command", "") if isinstance(h, dict) else ""
                        if any(pattern in cmd for pattern in _ORPHANED_HOOK_PATTERNS):
                            has_orphaned = True
                            break
                    if has_orphaned:
                        continue
                filtered.append(entry)
            hooks[event_type] = filtered

    return settings


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


def count_files_recursive(directory: str | Path) -> int:
    """Count all files recursively in *directory*.

    Returns 0 if the directory does not exist.
    """
    directory = Path(directory)
    if not directory.is_dir():
        return 0
    count = 0
    for entry in directory.iterdir():
        if entry.is_symlink():
            continue
        if entry.is_dir():
            count += count_files_recursive(entry)
        else:
            count += 1
    return count


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
    codex_skills_dir: str | Path | None = None,
) -> dict[str, object]:
    """Write a file manifest after installation for future modification detection.

    Returns the manifest dict.
    """
    config_dir = Path(config_dir)
    gpd_dir = config_dir / "get-physics-done"
    commands_dir = config_dir / "commands" / "gpd"
    agents_dir = config_dir / "agents"

    manifest: dict[str, object] = {
        "version": version,
        "timestamp": _iso_now(),
        "files": {},
    }
    files: dict[str, str] = {}

    # get-physics-done/
    for rel, h in generate_manifest(gpd_dir).items():
        files["get-physics-done/" + rel] = h

    # commands/gpd/
    if commands_dir.exists():
        for rel, h in generate_manifest(commands_dir).items():
            files["commands/gpd/" + rel] = h

    # agents/gpd-*.md
    if agents_dir.exists():
        for f in sorted(agents_dir.iterdir()):
            if f.name.startswith("gpd-") and f.suffix == ".md":
                files["agents/" + f.name] = file_hash(f)

    # Codex skills
    if codex_skills_dir:
        skills = Path(codex_skills_dir)
        if skills.exists():
            for entry in sorted(skills.iterdir()):
                if entry.is_dir() and entry.name.startswith("gpd-"):
                    skill_md = entry / "SKILL.md"
                    if skill_md.exists():
                        files[f"skills/{entry.name}/SKILL.md"] = file_hash(skill_md)

    manifest["files"] = files
    manifest_path = config_dir / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


# ---------------------------------------------------------------------------
# Local patch persistence
# ---------------------------------------------------------------------------


def save_local_patches(
    config_dir: str | Path,
    *,
    codex_skills_dir: str | Path | None = None,
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

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    codex_skills = Path(codex_skills_dir) if codex_skills_dir else Path(get_codex_skills_dir())
    patches_dir = config_dir / PATCHES_DIR_NAME
    modified: list[str] = []

    for rel_path, original_hash in (manifest.get("files") or {}).items():
        if rel_path.startswith("skills/"):
            full_path = codex_skills / rel_path[len("skills/") :]
        else:
            full_path = config_dir / rel_path

        if not full_path.exists():
            continue

        current = file_hash(full_path)
        if current != original_hash:
            backup_path = patches_dir / rel_path
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            import shutil

            shutil.copy2(str(full_path), str(backup_path))
            modified.append(rel_path)

    if modified:
        meta = {
            "backed_up_at": _iso_now(),
            "from_version": manifest.get("version", "unknown"),
            "files": modified,
        }
        meta_path = patches_dir / "backup-meta.json"
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

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
                f"Package integrity check failed: missing {required}/. "
                "Try reinstalling: pip install --force-reinstall get-physics-done"
            )


def compute_path_prefix(target_dir: Path, config_dir_name: str, *, is_global: bool, explicit_target: bool = False) -> str:
    """Compute the path prefix for placeholder replacement.

    Global installs use absolute path; local installs use ``./.<config_dir>/``.
    """
    if is_global or explicit_target:
        return str(target_dir).replace("\\", "/") + "/"
    return f"./{config_dir_name}/"


def pre_install_cleanup(
    target_dir: Path,
    *,
    codex_skills_dir: str | None = None,
) -> None:
    """Common pre-install cleanup: remove stale patches, save local patches, clean orphans."""
    import shutil as _shutil

    patches_dir = target_dir / PATCHES_DIR_NAME
    if patches_dir.exists():
        _shutil.rmtree(patches_dir)

    save_local_patches(target_dir, codex_skills_dir=codex_skills_dir)
    cleanup_orphaned_files(target_dir)

    gpd_dir = target_dir / "get-physics-done"
    if gpd_dir.exists():
        _shutil.rmtree(gpd_dir)

    hooks_dir = target_dir / "hooks"
    if hooks_dir.is_dir():
        for hook_name in HOOK_SCRIPTS.values():
            hook_path = hooks_dir / hook_name
            if hook_path.exists():
                hook_path.unlink()
        for hook_path in hooks_dir.iterdir():
            if hook_path.is_file() and hook_path.stem in LEGACY_HOOK_BASENAMES:
                hook_path.unlink()


def install_gpd_content(
    specs_dir: Path,
    target_dir: Path,
    path_prefix: str,
    runtime: str,
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
            copy_with_path_replacement(src_subdir, gpd_dest / subdir_name, path_prefix, runtime)

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

    hooks_dest = target_dir / "hooks"
    hooks_dest.mkdir(parents=True, exist_ok=True)
    for hook_file in hooks_src.iterdir():
        if hook_file.is_file() and not hook_file.name.startswith("__"):
            _shutil.copy2(hook_file, hooks_dest / hook_file.name)

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


def ensure_update_hook(settings: dict[str, object], update_check_command: str) -> None:
    """Add SessionStart update-check hook if not already present.

    Works for any runtime using settings.json hooks (Claude Code, Gemini).
    """
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        settings["hooks"] = hooks

    session_start = hooks.setdefault("SessionStart", [])
    if not isinstance(session_start, list):
        session_start = []
        hooks["SessionStart"] = session_start

    for entry in session_start:
        if not isinstance(entry, dict):
            continue
        entry_hooks = entry.get("hooks")
        if not isinstance(entry_hooks, list):
            continue
        for h in entry_hooks:
            if not isinstance(h, dict):
                continue
            cmd = h.get("command", "")
            if isinstance(cmd, str) and ("gpd-check-update" in cmd or "check_update" in cmd):
                return

    session_start.append({"hooks": [{"type": "command", "command": update_check_command}]})
    _install_logger.info("Configured update check hook")


def finish_install(
    settings_path: str | Path,
    settings: dict[str, object],
    statusline_command: str,
    should_install_statusline: bool,
    *,
    force_statusline: bool = False,
) -> None:
    """Apply statusline config and write settings atomically.

    Shared by Claude Code and Gemini adapters (both use settings.json).
    """
    if should_install_statusline:
        status_line = settings.get("statusLine")
        existing_cmd = status_line.get("command") if isinstance(status_line, dict) else None

        if (
            isinstance(existing_cmd, str)
            and "gpd-statusline" not in existing_cmd
            and "statusline" not in existing_cmd
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

    Shared by Claude Code and Gemini adapters.
    """
    command_interpreter = interpreter or _hook_python_interpreter()
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


def _hook_python_interpreter() -> str:
    """Return the interpreter that is currently running GPD.

    Hook scripts import ``gpd.*`` modules, so they need the same interpreter
    used for the active install process.
    """
    return sys.executable or "python3"


def _iso_now() -> str:
    """Return the current UTC time in ISO 8601 format."""
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
