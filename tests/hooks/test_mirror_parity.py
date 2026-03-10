"""Parity checks for mirrored runtime hook files."""

from __future__ import annotations

from pathlib import Path


def test_claude_hook_mirrors_match_source_hooks() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source_dir = repo_root / "src" / "gpd" / "hooks"
    mirror_dir = repo_root / ".claude" / "hooks"

    hook_names = (
        "runtime_detect.py",
        "statusline.py",
        "check_update.py",
        "codex_notify.py",
    )

    for hook_name in hook_names:
        assert (mirror_dir / hook_name).read_text(encoding="utf-8") == (
            source_dir / hook_name
        ).read_text(encoding="utf-8"), hook_name


def test_codex_hook_mirrors_match_source_hooks() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source_dir = repo_root / "src" / "gpd" / "hooks"
    mirror_dir = repo_root / ".codex" / "hooks"

    hook_names = (
        "runtime_detect.py",
        "statusline.py",
        "check_update.py",
        "codex_notify.py",
    )

    for hook_name in hook_names:
        assert (mirror_dir / hook_name).read_text(encoding="utf-8") == (
            source_dir / hook_name
        ).read_text(encoding="utf-8"), hook_name
