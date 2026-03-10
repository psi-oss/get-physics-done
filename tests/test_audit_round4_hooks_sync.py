"""Audit round 4: Hook file sync regression test.

Verifies that the hook files distributed under .codex/hooks/ and .claude/hooks/
remain byte-identical to the canonical sources in src/gpd/hooks/.  Any drift
between these copies indicates a sync was missed after editing the canonical
source.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

CANONICAL_DIR = REPO_ROOT / "src" / "gpd" / "hooks"

HOOK_FILES = [
    "check_update.py",
    "codex_notify.py",
    "runtime_detect.py",
    "statusline.py",
]

MIRROR_DIRS = [
    REPO_ROOT / ".codex" / "hooks",
    REPO_ROOT / ".claude" / "hooks",
]


class TestHooksSync:
    """Ensure .codex/hooks/ and .claude/hooks/ mirror src/gpd/hooks/ exactly."""

    @pytest.mark.parametrize("mirror_dir", MIRROR_DIRS, ids=lambda d: d.relative_to(REPO_ROOT).as_posix())
    @pytest.mark.parametrize("filename", HOOK_FILES)
    def test_hook_file_matches_canonical(self, mirror_dir: Path, filename: str) -> None:
        canonical = CANONICAL_DIR / filename
        mirror = mirror_dir / filename

        assert canonical.exists(), f"Canonical source missing: {canonical}"
        assert mirror.exists(), f"Mirror file missing: {mirror}"

        canonical_content = canonical.read_text(encoding="utf-8")
        mirror_content = mirror.read_text(encoding="utf-8")

        assert mirror_content == canonical_content, (
            f"{mirror.relative_to(REPO_ROOT)} differs from "
            f"{canonical.relative_to(REPO_ROOT)}. "
            f"Run: cp {canonical} {mirror}"
        )
