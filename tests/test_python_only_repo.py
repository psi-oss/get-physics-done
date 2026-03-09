"""Repository-level guardrails for the Python migration boundary."""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_bin_install_js_is_the_only_repo_javascript_file() -> None:
    repo_root = _repo_root()
    excluded_dirs = {".git", ".venv", "__pycache__", ".pytest_cache"}
    js_files = sorted(
        path.relative_to(repo_root).as_posix()
        for path in repo_root.rglob("*.js")
        if not any(part in excluded_dirs for part in path.parts)
    )

    assert js_files == ["bin/install.js"]


def test_legacy_gpd_javascript_hook_filenames_are_gone() -> None:
    repo_root = _repo_root()
    legacy_markers = (
        "gpd-statusline.js",
        "gpd-check-update.js",
        "gpd-codex-notify.js",
    )

    files_to_scan = [
        *repo_root.joinpath("src").rglob("*"),
        *repo_root.joinpath("tests").rglob("*"),
        repo_root / "README.md",
    ]

    offending: list[str] = []
    for path in files_to_scan:
        if not path.is_file():
            continue
        if path == Path(__file__).resolve():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(marker in content for marker in legacy_markers):
            offending.append(path.relative_to(repo_root).as_posix())

    assert offending == []
