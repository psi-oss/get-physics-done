from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

from scripts.release_workflow import (
    ReleaseError,
    validate_npm_pack_manifest,
    validate_package_data_rules,
    validate_release_metadata_sources,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_package_json_versions_match_pyproject_version() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_json = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))

    pyproject_version = pyproject["project"]["version"]
    assert package_json["version"] == pyproject_version
    assert package_json["gpdPythonVersion"] == pyproject_version


def test_release_metadata_sources_reject_version_mismatch() -> None:
    pyproject_text = '[project]\nname = "get-physics-done"\nversion = "1.2.3"\n'
    package_json_text = '{"version":"1.2.2","gpdPythonVersion":"1.2.3","files":["bin/install.js"]}'

    with pytest.raises(ReleaseError, match="Version source-of-truth mismatch"):
        validate_release_metadata_sources(pyproject_text, package_json_text)


def test_package_data_rules_reject_duplicate_force_include_destinations() -> None:
    pyproject_text = """
[project]
name = "get-physics-done"
version = "1.2.3"

[tool.hatch.build.targets.wheel]
artifacts = ["src/gpd/core/*.json"]

[tool.hatch.build.targets.wheel.force-include]
"src/gpd/core/one.json" = "gpd/core/shared.json"
"src/gpd/core/two.json" = "gpd/core/shared.json"
"""
    package_json_text = '{"version":"1.2.3","gpdPythonVersion":"1.2.3","files":["bin/install.js"]}'

    with pytest.raises(ReleaseError, match='force-include" destinations must be unique'):
        validate_package_data_rules(pyproject_text, package_json_text)


@pytest.mark.parametrize("entries", [1, True, "abc", {"files": []}])
def test_validate_npm_pack_manifest_rejects_non_list_roots(entries: object) -> None:
    with pytest.raises(ReleaseError, match="npm pack output root must be a list."):
        validate_npm_pack_manifest(entries)


@pytest.mark.parametrize("entries", [[1], ["x"], [None], [[]]])
def test_validate_npm_pack_manifest_rejects_non_object_entries(entries: object) -> None:
    with pytest.raises(ReleaseError, match="npm pack entry must be an object."):
        validate_npm_pack_manifest(entries)


@pytest.mark.parametrize(
    "entries",
    [[{"files": [1]}], [{"files": ["x"]}], [{"files": [None]}], [{"files": [[1]]}]],
)
def test_validate_npm_pack_manifest_rejects_non_object_file_entries(entries: object) -> None:
    with pytest.raises(ReleaseError, match='npm pack entry "files" must be a list of objects.'):
        validate_npm_pack_manifest(entries)


@pytest.mark.parametrize("entries", [[{"files": [{}]}], [{"files": [{"path": 3}]}]])
def test_validate_npm_pack_manifest_preserves_missing_resource_errors_for_bad_paths(entries: object) -> None:
    with pytest.raises(ReleaseError, match="npm pack is missing required resources:"):
        validate_npm_pack_manifest(entries)


def test_release_metadata_checks_accept_current_repo_configuration() -> None:
    pyproject_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    package_json_text = (REPO_ROOT / "package.json").read_text(encoding="utf-8")

    assert validate_release_metadata_sources(pyproject_text, package_json_text)
    validate_package_data_rules(pyproject_text, package_json_text)


def test_package_json_lint_package_checks_exact_head_commit_range() -> None:
    package_json = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    scripts = package_json["scripts"]
    assert isinstance(scripts, dict)

    lint_package = scripts["lint:package"]
    assert isinstance(lint_package, str)
    assert "check-human-authors.sh --range HEAD^!" in lint_package
    assert "HEAD~0..HEAD" not in lint_package
