"""Guardrails for public release consistency."""

from __future__ import annotations

import json
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _project_script_lines(repo_root: Path) -> list[str]:
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8").splitlines()
    collecting = False
    script_lines: list[str] = []
    for line in pyproject:
        stripped = line.strip()
        if stripped == "[project.scripts]":
            collecting = True
            continue
        if collecting and stripped.startswith("["):
            break
        if collecting and stripped:
            script_lines.append(stripped)
    return script_lines


def test_required_public_release_artifacts_exist() -> None:
    repo_root = _repo_root()
    required = (
        "README.md",
        "LICENSE",
        "CITATION.cff",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
    )

    missing = [path for path in required if not (repo_root / path).is_file()]
    assert missing == []


def test_public_docs_acknowledge_psi_and_gsd_inspiration() -> None:
    repo_root = _repo_root()

    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    assert "Physical Superintelligence (PSI)" in readme
    assert "GSD" in readme
    assert "[Physical Superintelligence (PSI)](https://www.psi.inc)" in readme

    user_guide = (repo_root / "docs/USER-GUIDE.md").read_text(encoding="utf-8")
    assert "Physical Superintelligence (PSI)" in user_guide
    assert "GSD" in user_guide
    assert "get-shit-done-cc" in user_guide


def test_public_bootstrap_package_exposes_npx_installer() -> None:
    repo_root = _repo_root()
    package_json = json.loads((repo_root / "package.json").read_text(encoding="utf-8"))

    assert package_json["name"] == "get-physics-done"
    assert package_json.get("bin", {}).get("get-physics-done") == "bin/install.js"
    assert "bin/" in package_json.get("files", [])
    assert (repo_root / "bin" / "install.js").is_file()


def test_public_bootstrap_installer_uses_python_cli_without_uv() -> None:
    repo_root = _repo_root()
    content = (repo_root / "bin" / "install.js").read_text(encoding="utf-8")

    assert "uv" not in content
    assert "gpd.cli" in content


def test_public_cli_surface_is_unified() -> None:
    repo_root = _repo_root()
    script_lines = _project_script_lines(repo_root)
    script_names = [line.split("=", 1)[0].strip().strip('"') for line in script_lines]

    assert 'gpd = "gpd.cli:app"' in script_lines
    assert all(name == "gpd" or name.startswith("gpd-mcp-") for name in script_names)
    assert sorted(path.name for path in (repo_root / "src" / "gpd").glob("cli*.py")) == ["cli.py"]


def test_install_docs_use_only_public_npx_flow() -> None:
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


def test_infra_descriptors_reference_public_bootstrap_flow() -> None:
    repo_root = _repo_root()
    expected = "npx github:physicalsuperintelligence/get-physics-done"
    stale_markers = (
        "packages/gpd",
        "uv pip install -e",
        "pip install -e packages/gpd",
    )

    for path in sorted((repo_root / "infra").glob("gpd-*.json")):
        content = path.read_text(encoding="utf-8")
        assert expected in content, f"{path.name} should reference the public bootstrap flow"
        for marker in stale_markers:
            assert marker not in content, f"{path.name} should not mention {marker!r}"


def test_manual_test_plan_covers_public_readme_install() -> None:
    repo_root = _repo_root()
    content = (repo_root / "MANUAL-TEST-PLAN.md").read_text(encoding="utf-8")

    assert "Phase 0: Public Release Smoke Test" in content
    assert "npx github:physicalsuperintelligence/get-physics-done" in content
    assert "follow only the public README instructions" in content


def test_initial_release_date_matches_launch_plan() -> None:
    repo_root = _repo_root()
    changelog = (repo_root / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "## [0.1.0] - 2026-03-15" in changelog
