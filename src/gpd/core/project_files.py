"""Legacy planning-file migration helpers."""

from __future__ import annotations

from pathlib import Path


def migrate_root_planning_files(project_root: Path) -> list[str]:
    """Do not auto-copy root ROADMAP.md / PROJECT.md into GPD/.

    The historical auto-migration wrote during read-only command paths. Keep
    this public hook as a no-op so those paths stay side-effect free.

    Returns an empty list because no files are migrated automatically.
    """
    return []
