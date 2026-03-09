"""Repository-level guardrails for the Python migration boundary."""

from __future__ import annotations

import json
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_bin_install_js_is_the_only_repo_javascript_file() -> None:
    repo_root = _repo_root()
    excluded_dirs = {"__pycache__"}
    js_files = sorted(
        path.relative_to(repo_root).as_posix()
        for path in repo_root.rglob("*.js")
        if not any(part in excluded_dirs or part.startswith(".") for part in path.relative_to(repo_root).parts[:-1])
    )

    assert js_files == ["bin/install.js"]


def test_package_json_exposes_npx_installer() -> None:
    repo_root = _repo_root()
    package_json = json.loads((repo_root / "package.json").read_text(encoding="utf-8"))

    assert package_json["name"] == "get-physics-done"
    assert package_json.get("bin", {}).get("get-physics-done") == "bin/install.js"
    assert "bin/" in package_json.get("files", [])
    assert (repo_root / "bin" / "install.js").is_file()


def test_npx_installer_no_longer_references_uv() -> None:
    repo_root = _repo_root()
    content = (repo_root / "bin" / "install.js").read_text(encoding="utf-8")

    assert "uv" not in content
    assert "gpd.cli" in content


def test_pyproject_exposes_single_gpd_cli_entrypoint() -> None:
    repo_root = _repo_root()
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")

    assert 'gpd = "gpd.cli:app"' in pyproject
    assert '"gpd+"' not in pyproject
    assert not (repo_root / "src" / "gpd" / "cli_plus.py").exists()


def test_unified_gpd_surface_has_no_cli_plus_regressions() -> None:
    repo_root = _repo_root()
    regression_markers = ("gpd+", "GPD+", "cli_plus")
    scan_targets = [
        repo_root / "src",
        repo_root / "docs",
        repo_root / "README.md",
        repo_root / "ARCHITECTURE.md",
        repo_root / "MANUAL-TEST-PLAN.md",
        repo_root / "pyproject.toml",
    ]

    offending: list[str] = []
    for target in scan_targets:
        paths = [target] if target.is_file() else target.rglob("*")
        for path in paths:
            if not path.is_file():
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if any(marker in content for marker in regression_markers):
                offending.append(path.relative_to(repo_root).as_posix())

    assert offending == []


def test_install_docs_are_npx_only() -> None:
    repo_root = _repo_root()
    npx_command = "npx github:physicalsuperintelligence/get-physics-done"
    disallowed_markers = (
        "uv tool install",
        "python3 -m pip install",
        "gpd install",
    )

    for relative_path in ("README.md", "docs/USER-GUIDE.md"):
        content = (repo_root / relative_path).read_text(encoding="utf-8")
        assert npx_command in content, f"{relative_path} should mention the npx bootstrap installer"
        for marker in disallowed_markers:
            assert marker not in content, f"{relative_path} should not mention {marker!r}"


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
