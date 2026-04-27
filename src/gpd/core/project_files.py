"""Auto-migrate planning files from workspace root into GPD/."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path

from gpd.core.constants import PLANNING_DIR_NAME, PROJECT_FILENAME, ROADMAP_FILENAME

logger = logging.getLogger("gpd")

_MIGRATABLE_FILES = (ROADMAP_FILENAME, PROJECT_FILENAME)


def _atomic_copy2(src: Path, dst: Path) -> None:
    """Copy metadata-preserving content into place with a same-directory rename."""

    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=dst.parent, prefix=f".{dst.name}.", suffix=".tmp")
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        shutil.copy2(src, tmp_path)
        os.replace(tmp_path, dst)
        tmp_path = None
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass


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
        if gpd_path.exists() or gpd_path.is_symlink() or not root_path.exists():
            continue
        try:
            _atomic_copy2(root_path, gpd_path)
            migrated.append(filename)
            logger.info("Copied %s from project root to %s/", filename, PLANNING_DIR_NAME)
        except OSError as exc:
            # Remove partial copy so next run retries from intact root
            if not gpd_path.is_symlink():
                gpd_path.unlink(missing_ok=True)
            logger.warning("Could not copy %s to %s/: %s", filename, PLANNING_DIR_NAME, exc)
    return migrated
