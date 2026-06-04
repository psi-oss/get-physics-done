#!/usr/bin/env python3
"""Stop hook — automatic Mayfly session capture.

Fires after each agent response. When a GPD project with an initialized
Mayfly notebook is detected and a GPD command has been executed since the
last capture, appends a raw session record to GPD/mayfly/session-log.jsonl.

No LLM call. No user action required. Exits cleanly when the project has no
Mayfly notebook (not all projects need one).

The session log is a raw capture buffer — agents synthesize it into the
knowledge graph via the gpd-mayfly MCP tools.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# Max entries to read from the lineage ledger when scanning for new commands.
_LINEAGE_SCAN_LINES = 200

# Max parent directories to walk looking for a GPD project root.
_MAX_PARENT_WALK = 8


def _find_project_root(cwd: Path) -> Path | None:
    """Walk upward to find a directory containing a GPD/ subdirectory."""
    current = cwd.resolve()
    for _ in range(_MAX_PARENT_WALK):
        if (current / "GPD").is_dir():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _read_last_capture_ts(session_log: Path) -> str | None:
    """Return the timestamp of the most recent capture entry, or None."""
    if not session_log.exists():
        return None
    try:
        text = session_log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    last_ts = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if isinstance(entry, dict) and "ts" in entry:
                last_ts = entry["ts"]
        except (json.JSONDecodeError, ValueError):
            continue
    return last_ts


def _read_recent_commands(lineage_ledger: Path, since_ts: str | None) -> list[str]:
    """Return GPD command names from lineage entries newer than since_ts."""
    if not lineage_ledger.exists():
        return []
    try:
        text = lineage_ledger.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    # Only scan the tail to bound work.
    recent = lines[-_LINEAGE_SCAN_LINES:]

    commands: list[str] = []
    for line in recent:
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(entry, dict):
            continue
        recorded_at = entry.get("recorded_at", "")
        if since_ts and recorded_at <= since_ts:
            continue
        # Look for source_name (the command that was run)
        source_name = entry.get("source_name") or entry.get("data", {}).get("command", "")
        if source_name and isinstance(source_name, str):
            commands.append(source_name)
    return commands


def _append_session_log(session_log: Path, record: dict) -> None:
    """Append a JSON record line to the session log."""
    session_log.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, separators=(",", ":")) + "\n"
    try:
        with session_log.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass  # Non-fatal: hook is best-effort


def _bootstrap_mayfly_dirs(mayfly_dir: Path) -> None:
    """Create the mayfly directory structure silently if GPD project is active."""
    if mayfly_dir.exists():
        return
    # Only bootstrap if we're clearly in a GPD project with state
    gpd_dir = mayfly_dir.parent
    if not (gpd_dir / "state.json").exists() and not (gpd_dir / "PROJECT.md").exists():
        return
    try:
        for subdir in ("knowledge", "sessions", "epochs"):
            (mayfly_dir / subdir).mkdir(parents=True, exist_ok=True)

        frontier = mayfly_dir / "FRONTIER.md"
        if not frontier.exists():
            frontier.write_text(
                "# Campaign Frontier — (not yet started)\n\n"
                "## Current best\nNo sessions yet.\n\n"
                "## Most promising open directions\n(Fill in when research begins.)\n\n"
                "## Active hypotheses\n(None yet.)\n\n"
                "## Known dead ends\n(None yet.)\n\n"
                "## Knowledge index\n→ knowledge/MAP.md\n",
                encoding="utf-8",
            )

        knowledge_map = mayfly_dir / "knowledge" / "MAP.md"
        if not knowledge_map.exists():
            knowledge_map.write_text(
                "# Knowledge Map — (not yet started)\n\n"
                "## Active topics\n(None yet.)\n\n"
                "## Closed / dead-end topics\n(None yet.)\n\n"
                "## Epoch index\n(None yet.)\n\n"
                "## Open research questions\n(Seed from problem statement.)\n",
                encoding="utf-8",
            )

        journal = mayfly_dir / "JOURNAL.md"
        if not journal.exists():
            journal.write_text(
                "# Mayfly Research Journal\n\n"
                "| step | outcome | summary | knowledge_updated | files |\n"
                "|---:|---|---|---|---|\n",
                encoding="utf-8",
            )
    except OSError:
        pass  # Non-fatal


def main() -> int:
    # Read hook payload from stdin.
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError, OSError):
        payload = {}

    if not isinstance(payload, dict):
        payload = {}

    # Extract cwd. The runtime Stop hook provides this directly or via
    # workspace info. Fall back to the process working directory.
    cwd_str = payload.get("cwd") or payload.get("workspace_root") or payload.get("project_root") or os.getcwd()
    if not cwd_str:
        return 0

    try:
        cwd = Path(str(cwd_str))
    except (TypeError, ValueError):
        return 0

    project_root = _find_project_root(cwd)
    if project_root is None:
        return 0

    gpd_dir = project_root / "GPD"
    mayfly_dir = gpd_dir / "mayfly"

    # Bootstrap silently when a GPD project is active but mayfly isn't
    # initialized yet — this handles the "first session after install" case.
    if not mayfly_dir.exists():
        _bootstrap_mayfly_dirs(mayfly_dir)
        # Even if we just bootstrapped, nothing substantive happened yet.
        return 0

    session_log = mayfly_dir / "session-log.jsonl"
    lineage_ledger = gpd_dir / "lineage" / "execution-lineage.jsonl"

    last_ts = _read_last_capture_ts(session_log)
    commands = _read_recent_commands(lineage_ledger, since_ts=last_ts)

    if not commands:
        # Nothing new happened that involves GPD — skip.
        return 0

    # Build the capture record.
    session_id = str(payload.get("session_id") or payload.get("session") or "")
    transcript_path = str(payload.get("transcript_path") or "")
    stop_reason = str(payload.get("stop_reason") or "")

    record: dict[str, object] = {
        "ts": datetime.now(UTC).isoformat(),
        "session_id": session_id[:64] if session_id else "",
        "commands_run": list(dict.fromkeys(commands)),  # deduplicate, preserve order
        "synthesis_status": "pending",
    }
    if transcript_path:
        record["transcript_path"] = transcript_path
    if stop_reason:
        record["stop_reason"] = stop_reason

    _append_session_log(session_log, record)
    return 0


if __name__ == "__main__":
    sys.exit(main())
