"""Auto-migrate planning files from workspace root into GPD/."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from gpd.core.constants import PLANNING_DIR_NAME, PROJECT_FILENAME, ROADMAP_FILENAME

logger = logging.getLogger("gpd")

_MIGRATABLE_FILES = (ROADMAP_FILENAME, PROJECT_FILENAME)


def migrate_root_planning_files(project_root: Path) -> list[str]:
    """Copy ROADMAP.md and PROJECT.md from root to GPD/ if not already there.

    Idempotent: files already in GPD/ are skipped. Errors are logged as
    warnings and do not abort the caller.

    Returns list of migrated filenames.
    """
    gpd_dir = project_root / PLANNING_DIR_NAME
    migrated: list[str] = []
    for filename in _MIGRATABLE_FILES:
        gpd_path = gpd_dir / filename
        root_path = project_root / filename
        if gpd_path.exists() or not root_path.exists():
            continue
        try:
            gpd_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root_path, gpd_path)
            migrated.append(filename)
            logger.info("Copied %s from project root to %s/", filename, PLANNING_DIR_NAME)
        except OSError as exc:
            # Remove partial copy so next run retries from intact root
            gpd_path.unlink(missing_ok=True)
            logger.warning("Could not copy %s to %s/: %s", filename, PLANNING_DIR_NAME, exc)
    return migrated
