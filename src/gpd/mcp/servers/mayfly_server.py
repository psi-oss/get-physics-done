"""MCP server for the GPD Mayfly research-campaign notebook.

Manages the depth-tiered knowledge graph under GPD/mayfly/:
  FRONTIER.md        — current knowledge state (1 page, read by PI first)
  knowledge/MAP.md   — topic navigation index
  knowledge/<topic>  — per-topic synthesis with provenance links
  epochs/<range>     — compressed session history
  sessions/<NNN>     — per-session raw notes
  JOURNAL.md         — append-only one-row-per-session log
  session-log.jsonl  — raw automatic capture from Stop hook

Usage:
    python -m gpd.mcp.servers.mayfly_server
    # or via entry point:
    gpd-mcp-mayfly
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import WithJsonSchema

from gpd.core.constants import ProjectLayout
from gpd.core.utils import atomic_write, safe_read_file
from gpd.mcp.servers import (
    ABSOLUTE_PROJECT_DIR_SCHEMA,
    configure_mcp_logging,
    mutating_tool_annotations,
    read_only_tool_annotations,
    resolve_absolute_project_dir,
    stable_mcp_error,
    stable_mcp_response,
    tighten_registered_tool_contracts,
)

logger = configure_mcp_logging("gpd-mayfly")

mcp = FastMCP("gpd-mayfly")

AbsoluteProjectDirInput = Annotated[str, WithJsonSchema(ABSOLUTE_PROJECT_DIR_SCHEMA)]

_READ_ANNOTATIONS = read_only_tool_annotations()
_WRITE_ANNOTATIONS = mutating_tool_annotations(destructive=False, idempotent=True)

# Reserved filenames inside knowledge/ that are not topic slugs.
_RESERVED_KNOWLEDGE_NAMES = frozenset({"MAP", "INDEX", "README"})

# Maximum lines returned by search_notebook.
_SEARCH_MAX_LINES = 80

# Maximum session-log entries returned by read_session_log.
_SESSION_LOG_MAX_ENTRIES = 50


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _mayfly_dir(project_root: Path) -> Path:
    return ProjectLayout(project_root).mayfly_dir


def _sanitize_topic(topic: str) -> str | None:
    """Return a safe slug for a knowledge topic, or None if invalid."""
    slug = topic.strip().lower()
    # Allow only alphanumeric, hyphens, underscores. No path separators.
    slug = re.sub(r"[^a-z0-9_-]", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    if not slug or slug.upper() in _RESERVED_KNOWLEDGE_NAMES:
        return None
    return slug


def _sanitize_epoch_name(name: str) -> str | None:
    """Return a safe filename for an epoch, or None if invalid."""
    # Expect format: NNN-NNN (e.g. "000-019")
    stripped = name.strip().rstrip(".md")
    if not re.fullmatch(r"\d{3}-\d{3}", stripped):
        return None
    return stripped


def _stub(path: Path, description: str) -> str:
    return f"({description} — {path.name} does not exist yet)"


def _read_or_stub(path: Path, stub_description: str) -> str:
    content = safe_read_file(path)
    if content is None:
        return _stub(path, stub_description)
    return content


def _ensure_mayfly_dirs(mayfly_dir: Path) -> None:
    """Create the notebook directory tree if it doesn't exist."""
    for subdir in ("knowledge", "sessions", "epochs"):
        (mayfly_dir / subdir).mkdir(parents=True, exist_ok=True)


def _is_initialized(mayfly_dir: Path) -> bool:
    return mayfly_dir.exists()


def _search_file(path: Path, query: str, results: list[str]) -> None:
    """Append matching lines from a file to results."""
    content = safe_read_file(path)
    if not content:
        return
    q = query.lower()
    for i, line in enumerate(content.splitlines(), 1):
        if q in line.lower():
            results.append(f"{path.name}:{i}: {line}")


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


@mcp.tool(annotations=_WRITE_ANNOTATIONS)
def bootstrap_mayfly(project_dir: AbsoluteProjectDirInput) -> dict:
    """Initialize the Mayfly notebook directory structure for a GPD project.

    Creates GPD/mayfly/ with all required subdirectories and seed files if
    they don't already exist. Idempotent — safe to call on an already-
    initialized project.

    Args:
        project_dir: Absolute path to the project root directory.
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")

    layout = ProjectLayout(cwd)
    mayfly = layout.mayfly_dir

    if mayfly.exists():
        return stable_mcp_response({"initialized": False, "message": "Mayfly notebook already initialized."})

    _ensure_mayfly_dirs(mayfly)

    # Seed FRONTIER.md
    atomic_write(
        layout.mayfly_frontier,
        "# Campaign Frontier — step 000 (not yet started)\n\n"
        "## Current best\nNo attempts yet.\n\n"
        "## Most promising open directions\n(Fill in from problem statement or seed material if available.)\n\n"
        "## Active hypotheses\n(None yet.)\n\n"
        "## Known dead ends\n(None yet.)\n\n"
        "## Knowledge index\n→ knowledge/MAP.md\n",
    )

    # Seed knowledge/MAP.md
    atomic_write(
        layout.mayfly_map,
        "# Knowledge Map — step 000 (not yet started)\n\n"
        "## Active topics\n(None yet.)\n\n"
        "## Closed / dead-end topics\n(None yet.)\n\n"
        "## Epoch index\n(None yet.)\n\n"
        "## Open research questions\n(Seed from problem statement if available.)\n",
    )

    # Seed JOURNAL.md
    atomic_write(
        layout.mayfly_journal,
        "# Mayfly Research Journal\n\n"
        "Append-only log of research sessions on this campaign. One row per session.\n\n"
        "| step | outcome | summary | knowledge_updated | files |\n"
        "|---:|---|---|---|---|\n",
    )

    return stable_mcp_response({"initialized": True, "message": f"Mayfly notebook initialized at {mayfly.as_posix()}"})


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------


@mcp.tool(annotations=_READ_ANNOTATIONS)
def read_frontier(project_dir: AbsoluteProjectDirInput) -> dict:
    """Return FRONTIER.md — the current campaign knowledge state.

    This is the PI's entry point. Read this first; only descend to deeper
    tiers if FRONTIER doesn't give enough signal.

    Args:
        project_dir: Absolute path to the project root directory.
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    layout = ProjectLayout(cwd)
    content = _read_or_stub(layout.mayfly_frontier, "no frontier yet")
    return stable_mcp_response({"content": content, "path": str(layout.mayfly_frontier)})


@mcp.tool(annotations=_READ_ANNOTATIONS)
def read_map(project_dir: AbsoluteProjectDirInput) -> dict:
    """Return knowledge/MAP.md — the navigable topic and epoch index.

    Read this after FRONTIER when you need to explore a specific angle or
    navigate to an epoch.

    Args:
        project_dir: Absolute path to the project root directory.
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    layout = ProjectLayout(cwd)
    content = _read_or_stub(layout.mayfly_map, "no map yet")
    return stable_mcp_response({"content": content, "path": str(layout.mayfly_map)})


@mcp.tool(annotations=_READ_ANNOTATIONS)
def list_knowledge(project_dir: AbsoluteProjectDirInput) -> dict:
    """Return a sorted list of topic slugs in knowledge/.

    Args:
        project_dir: Absolute path to the project root directory.
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    knowledge_dir = ProjectLayout(cwd).mayfly_knowledge_dir
    if not knowledge_dir.exists():
        return stable_mcp_response({"topics": []})
    slugs = sorted(p.stem for p in knowledge_dir.glob("*.md") if p.stem.upper() not in _RESERVED_KNOWLEDGE_NAMES)
    return stable_mcp_response({"topics": slugs})


@mcp.tool(annotations=_READ_ANNOTATIONS)
def read_knowledge(project_dir: AbsoluteProjectDirInput, topic: str) -> dict:
    """Return a knowledge topic entry (knowledge/<topic>.md).

    Args:
        project_dir: Absolute path to the project root directory.
        topic: Topic slug (lowercase, hyphens).
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    slug = _sanitize_topic(topic)
    if slug is None:
        return stable_mcp_error(f"Invalid topic slug: {topic!r}")
    path = ProjectLayout(cwd).mayfly_knowledge_dir / f"{slug}.md"
    content = _read_or_stub(path, f"no entry for topic '{slug}'")
    return stable_mcp_response({"content": content, "topic": slug, "path": str(path)})


@mcp.tool(annotations=_READ_ANNOTATIONS)
def read_journal(project_dir: AbsoluteProjectDirInput) -> dict:
    """Return JOURNAL.md — the append-only session log.

    This is archive-tier at scale. Prefer FRONTIER → MAP → knowledge for
    navigation; only read the journal for forensics.

    Args:
        project_dir: Absolute path to the project root directory.
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    layout = ProjectLayout(cwd)
    content = _read_or_stub(layout.mayfly_journal, "no journal entries yet")
    return stable_mcp_response({"content": content})


@mcp.tool(annotations=_READ_ANNOTATIONS)
def list_sessions(project_dir: AbsoluteProjectDirInput) -> dict:
    """Return sorted session-note filenames (deepest corner — reached via links).

    Args:
        project_dir: Absolute path to the project root directory.
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    sessions_dir = ProjectLayout(cwd).mayfly_sessions_dir
    if not sessions_dir.exists():
        return stable_mcp_response({"sessions": []})
    names = sorted(p.name for p in sessions_dir.glob("*.md"))
    return stable_mcp_response({"sessions": names})


@mcp.tool(annotations=_READ_ANNOTATIONS)
def read_session_notes(project_dir: AbsoluteProjectDirInput, step: int) -> dict:
    """Return full notes for one session (sessions/<NNN>.md).

    Args:
        project_dir: Absolute path to the project root directory.
        step: Zero-based session step number.
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    path = ProjectLayout(cwd).mayfly_sessions_dir / f"{step:03d}.md"
    content = _read_or_stub(path, f"no notes for session {step:03d}")
    return stable_mcp_response({"content": content, "step": step})


@mcp.tool(annotations=_READ_ANNOTATIONS)
def list_epochs(project_dir: AbsoluteProjectDirInput) -> dict:
    """Return sorted epoch summary filenames (archive tier).

    Args:
        project_dir: Absolute path to the project root directory.
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    epochs_dir = ProjectLayout(cwd).mayfly_epochs_dir
    if not epochs_dir.exists():
        return stable_mcp_response({"epochs": []})
    names = sorted(p.name for p in epochs_dir.glob("*.md"))
    return stable_mcp_response({"epochs": names})


@mcp.tool(annotations=_READ_ANNOTATIONS)
def read_epoch(project_dir: AbsoluteProjectDirInput, name: str) -> dict:
    """Return one epoch summary (epochs/<NNN-NNN>.md).

    Args:
        project_dir: Absolute path to the project root directory.
        name: Epoch filename without .md extension (e.g. "000-019").
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    safe_name = _sanitize_epoch_name(name)
    if safe_name is None:
        return stable_mcp_error(f"Invalid epoch name: {name!r}. Expected NNN-NNN format.")
    path = ProjectLayout(cwd).mayfly_epochs_dir / f"{safe_name}.md"
    content = _read_or_stub(path, f"no epoch summary for {safe_name}")
    return stable_mcp_response({"content": content, "name": safe_name})


@mcp.tool(annotations=_READ_ANNOTATIONS)
def read_session_log(project_dir: AbsoluteProjectDirInput, limit: int = 10) -> dict:
    """Return recent raw session-capture entries from session-log.jsonl.

    These are automatically written by the Stop hook and contain sessions
    that may not yet have been synthesized into the knowledge graph.

    Args:
        project_dir: Absolute path to the project root directory.
        limit: Maximum number of entries to return (most recent first).
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    log_path = ProjectLayout(cwd).mayfly_session_log
    if not log_path.exists():
        return stable_mcp_response({"entries": [], "total": 0})
    try:
        raw = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return stable_mcp_response({"entries": [], "total": 0})
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    total = len(lines)
    clamped = max(1, min(limit, _SESSION_LOG_MAX_ENTRIES))
    recent = lines[-clamped:]
    entries = []
    for line in reversed(recent):
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            entries.append({"raw": line})
    return stable_mcp_response({"entries": entries, "total": total})


@mcp.tool(annotations=_READ_ANNOTATIONS)
def search_notebook(project_dir: AbsoluteProjectDirInput, query: str) -> dict:
    """Case-insensitive substring search across all Mayfly notebook tiers.

    Searches FRONTIER.md, knowledge/*.md, epochs/*.md, JOURNAL.md,
    and sessions/*.md. Returns matching lines with source filenames.

    Args:
        project_dir: Absolute path to the project root directory.
        query: Case-insensitive search string.
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    if not query or not query.strip():
        return stable_mcp_error("query must be a non-empty string")

    layout = ProjectLayout(cwd)
    mayfly = layout.mayfly_dir
    if not mayfly.exists():
        return stable_mcp_response({"results": [], "message": "Mayfly notebook not initialized."})

    results: list[str] = []

    # Surface tier
    for path in (layout.mayfly_frontier, layout.mayfly_map, layout.mayfly_journal):
        _search_file(path, query, results)

    # Knowledge tier
    knowledge_dir = layout.mayfly_knowledge_dir
    if knowledge_dir.exists():
        for p in sorted(knowledge_dir.glob("*.md")):
            _search_file(p, query, results)

    # Archive tier — epochs
    epochs_dir = layout.mayfly_epochs_dir
    if epochs_dir.exists():
        for p in sorted(epochs_dir.glob("*.md")):
            _search_file(p, query, results)

    # Raw tier — sessions (last 50 only to bound output)
    sessions_dir = layout.mayfly_sessions_dir
    if sessions_dir.exists():
        for p in sorted(sessions_dir.glob("*.md"))[-50:]:
            _search_file(p, query, results)

    if len(results) > _SEARCH_MAX_LINES:
        truncated = len(results) - _SEARCH_MAX_LINES
        results = results[:_SEARCH_MAX_LINES]
        results.append(f"... {truncated} more lines truncated. Refine your query.")

    return stable_mcp_response({"results": results, "count": len(results)})


# ---------------------------------------------------------------------------
# Write tools
# ---------------------------------------------------------------------------


@mcp.tool(annotations=_WRITE_ANNOTATIONS)
def update_frontier(project_dir: AbsoluteProjectDirInput, content: str) -> dict:
    """Overwrite FRONTIER.md with updated campaign knowledge state.

    Called by the Researcher at the end of every session. Must reflect the
    current best result, open directions, active hypotheses, and dead ends.

    Args:
        project_dir: Absolute path to the project root directory.
        content: Full FRONTIER.md content to write.
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    if not content or not content.strip():
        return stable_mcp_error("content must be non-empty")
    layout = ProjectLayout(cwd)
    _ensure_mayfly_dirs(layout.mayfly_dir)
    atomic_write(layout.mayfly_frontier, content)
    return stable_mcp_response({"written": str(layout.mayfly_frontier)})


@mcp.tool(annotations=_WRITE_ANNOTATIONS)
def update_map(project_dir: AbsoluteProjectDirInput, content: str) -> dict:
    """Overwrite knowledge/MAP.md — the topic and epoch navigation index.

    The Researcher updates the topic list. The Summarizer appends to the
    epoch index. Neither should overwrite the other's section.

    Args:
        project_dir: Absolute path to the project root directory.
        content: Full MAP.md content to write.
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    if not content or not content.strip():
        return stable_mcp_error("content must be non-empty")
    layout = ProjectLayout(cwd)
    _ensure_mayfly_dirs(layout.mayfly_dir)
    atomic_write(layout.mayfly_map, content)
    return stable_mcp_response({"written": str(layout.mayfly_map)})


@mcp.tool(annotations=_WRITE_ANNOTATIONS)
def upsert_knowledge(project_dir: AbsoluteProjectDirInput, topic: str, content: str) -> dict:
    """Write or update a knowledge topic entry (knowledge/<topic>.md).

    Read the existing entry first with read_knowledge() to preserve prior
    evidence bullets and their provenance links. Every supporting-evidence
    bullet must carry a → session NNN link.

    Args:
        project_dir: Absolute path to the project root directory.
        topic: Topic slug (lowercase, hyphens). Created if it doesn't exist.
        content: Full topic entry content to write.
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    slug = _sanitize_topic(topic)
    if slug is None:
        return stable_mcp_error(f"Invalid topic slug: {topic!r}. Use lowercase letters, hyphens, underscores.")
    if not content or not content.strip():
        return stable_mcp_error("content must be non-empty")
    layout = ProjectLayout(cwd)
    _ensure_mayfly_dirs(layout.mayfly_dir)
    path = layout.mayfly_knowledge_dir / f"{slug}.md"
    created = not path.exists()
    atomic_write(path, content)
    return stable_mcp_response({"written": str(path), "topic": slug, "created": created})


@mcp.tool(annotations=_WRITE_ANNOTATIONS)
def write_session_notes(project_dir: AbsoluteProjectDirInput, step: int, content: str) -> dict:
    """Write full notes for one session (sessions/<NNN>.md).

    This is the deepest corner — raw detail, reached via links from knowledge
    entries and epoch summaries.

    Args:
        project_dir: Absolute path to the project root directory.
        step: Zero-based session step number.
        content: Full session notes content.
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    if step < 0:
        return stable_mcp_error("step must be a non-negative integer")
    if not content or not content.strip():
        return stable_mcp_error("content must be non-empty")
    layout = ProjectLayout(cwd)
    _ensure_mayfly_dirs(layout.mayfly_dir)
    path = layout.mayfly_sessions_dir / f"{step:03d}.md"
    atomic_write(path, content)
    return stable_mcp_response({"written": str(path), "step": step})


@mcp.tool(annotations=_WRITE_ANNOTATIONS)
def append_journal_row(
    project_dir: AbsoluteProjectDirInput,
    step: int,
    outcome: str,
    summary: str,
    knowledge_updated: str,
    files: str,
    metric: str = "",
) -> dict:
    """Append or upsert one row in JOURNAL.md for a completed session.

    The `knowledge_updated` field should list the topic slugs updated this
    session (comma-separated), making the journal a reverse index from
    step → topics.

    Args:
        project_dir: Absolute path to the project root directory.
        step: Zero-based session step number.
        outcome: One of: new_best, tied, regressed, partial, stalled, broken.
        summary: One-line summary of what was attempted and what came out.
        knowledge_updated: Comma-separated topic slugs updated this session.
        files: Key files written or modified (comma-separated, brief).
        metric: Optional numeric metric value (leave empty if no numeric metric).
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    if step < 0:
        return stable_mcp_error("step must be a non-negative integer")

    layout = ProjectLayout(cwd)
    _ensure_mayfly_dirs(layout.mayfly_dir)
    journal = layout.mayfly_journal

    # Build the new row
    step_str = f"{step:03d}"

    # Sanitize fields for Markdown table: replace pipes
    def _clean(s: str) -> str:
        return s.replace("|", "\\|").strip()

    if metric:
        new_row = f"| {step_str} | {_clean(metric)} | {_clean(outcome)} | {_clean(summary)} | {_clean(knowledge_updated)} | {_clean(files)} |\n"
    else:
        new_row = (
            f"| {step_str} | {_clean(outcome)} | {_clean(summary)} | {_clean(knowledge_updated)} | {_clean(files)} |\n"
        )

    # Read existing journal; upsert row for this step (replace if exists)
    existing = safe_read_file(journal) or ""
    lines = existing.splitlines(keepends=True)

    # Find and replace an existing row for this step, or append
    replaced = False
    new_lines: list[str] = []
    for line in lines:
        # Match a table row starting with | step_str |
        if re.match(rf"^\|\s*{re.escape(step_str)}\s*\|", line):
            new_lines.append(new_row)
            replaced = True
        else:
            new_lines.append(line)

    if not replaced:
        new_lines.append(new_row)

    atomic_write(journal, "".join(new_lines))
    return stable_mcp_response({"step": step, "replaced": replaced, "written": str(journal)})


@mcp.tool(annotations=_WRITE_ANNOTATIONS)
def write_epoch_summary(
    project_dir: AbsoluteProjectDirInput,
    start: int,
    end: int,
    content: str,
) -> dict:
    """Write a compressed epoch summary (epochs/<start>-<end>.md).

    Called by the Summarizer mayfly every EPOCH_SIZE sessions.

    Args:
        project_dir: Absolute path to the project root directory.
        start: First session step in this epoch (inclusive).
        end: Last session step in this epoch (inclusive).
        content: Full epoch summary content.
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    if start < 0 or end < start:
        return stable_mcp_error("start and end must satisfy 0 <= start <= end")
    if not content or not content.strip():
        return stable_mcp_error("content must be non-empty")
    layout = ProjectLayout(cwd)
    _ensure_mayfly_dirs(layout.mayfly_dir)
    path = layout.mayfly_epochs_dir / f"{start:03d}-{end:03d}.md"
    atomic_write(path, content)
    return stable_mcp_response({"written": str(path), "start": start, "end": end})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the gpd-mayfly MCP server."""
    from gpd.mcp.servers import run_mcp_server

    run_mcp_server(mcp, "GPD Mayfly Research Notebook MCP Server")


tighten_registered_tool_contracts(mcp)
