"""Fast packaging manifest checks for installed GPD runtime resources."""

from __future__ import annotations

import json
import tomllib
from fnmatch import fnmatchcase
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"
PACKAGE_JSON = REPO_ROOT / "package.json"


def _pyproject() -> dict[str, object]:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _package_json() -> dict[str, object]:
    return json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))


def test_python_wheel_declares_runtime_markdown_json_tex_resources() -> None:
    hatch_wheel = _pyproject()["tool"]["hatch"]["build"]["targets"]["wheel"]
    artifacts = hatch_wheel["artifacts"]

    assert {"src/gpd/agents/*", "src/gpd/agents/**/*"} <= set(artifacts)
    assert {"src/gpd/commands/*", "src/gpd/commands/**/*"} <= set(artifacts)
    assert {"src/gpd/hooks/*", "src/gpd/hooks/**/*"} <= set(artifacts)
    assert {"src/gpd/specs/*", "src/gpd/specs/**/*"} <= set(artifacts)
    assert "src/gpd/mcp/paper/templates/**/*" in artifacts
    assert "src/gpd/adapters/*.json" in artifacts
    assert "src/gpd/core/*.json" in artifacts


def test_python_wheel_manifest_covers_known_runtime_resource_examples() -> None:
    artifacts = _pyproject()["tool"]["hatch"]["build"]["targets"]["wheel"]["artifacts"]
    expected_examples = (
        Path("src/gpd/commands/plan-phase.md"),
        Path("src/gpd/agents/gpd-planner.md"),
        Path("src/gpd/specs/workflows/plan-phase.md"),
        Path("src/gpd/specs/workflows/plan-phase-stage-manifest.json"),
        Path("src/gpd/specs/templates/slides/main.tex"),
        Path("src/gpd/mcp/paper/templates/prl/prl_template.tex"),
        Path("src/gpd/hooks/statusline.py"),
        Path("src/gpd/hooks/check_update.py"),
        Path("src/gpd/adapters/runtime_catalog.json"),
        Path("src/gpd/core/public_surface_contract.json"),
    )

    for resource in expected_examples:
        assert resource.is_file(), f"fixture resource missing: {resource}"
        source_path = resource.as_posix()
        assert any(fnmatchcase(source_path, pattern) for pattern in artifacts), (
            f"{source_path} is not covered by wheel artifact globs"
        )


def test_python_wheel_manifest_covers_all_current_runtime_resources() -> None:
    hatch_wheel = _pyproject()["tool"]["hatch"]["build"]["targets"]["wheel"]
    artifacts = tuple(hatch_wheel["artifacts"])
    force_include = set(hatch_wheel["force-include"])
    runtime_resources = sorted(
        path.relative_to(REPO_ROOT)
        for suffix in ("*.md", "*.json", "*.tex")
        for path in (REPO_ROOT / "src" / "gpd").rglob(suffix)
    )

    assert runtime_resources
    for resource in runtime_resources:
        source_path = resource.as_posix()
        assert source_path in force_include or any(fnmatchcase(source_path, pattern) for pattern in artifacts), (
            f"{source_path} is not covered by wheel artifact globs or force-include"
        )


def test_npm_package_remains_bootstrap_plus_contract_manifests_only() -> None:
    package = _package_json()
    files = package["files"]

    assert package["bin"] == {"get-physics-done": "bin/install.js"}
    assert "bin/" in files
    assert "src/gpd/commands/" not in files
    assert "src/gpd/specs/" not in files
    assert "src/gpd/agents/" not in files
    assert all(not entry.endswith(".md") and not entry.endswith(".tex") for entry in files)
    assert set(files) == {
        "bin/",
        "src/gpd/adapters/runtime_catalog.json",
        "src/gpd/adapters/runtime_catalog_schema.json",
        "src/gpd/core/public_surface_contract_schema.json",
        "src/gpd/core/public_surface_contract.json",
    }
