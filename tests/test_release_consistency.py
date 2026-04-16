"""Guardrails for public release consistency."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tomllib
from importlib import import_module, resources
from pathlib import Path

import pytest

from gpd.adapters.install_utils import HOOK_SCRIPTS, bundled_hook_relpaths
from gpd.adapters.runtime_catalog import get_shared_install_metadata
from scripts.release_workflow import (
    ReleaseError,
    bump_version,
    extract_release_notes,
    prepare_release,
    stamp_publish_date,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


_SHARED_INSTALL = get_shared_install_metadata()
_BOOTSTRAP_JSON_ASSETS = (
    "src/gpd/adapters/runtime_catalog.json",
    "src/gpd/adapters/runtime_catalog_schema.json",
    "src/gpd/core/public_surface_contract.json",
    "src/gpd/core/public_surface_contract_schema.json",
)

_WHEEL_JSON_ASSETS = tuple(path.removeprefix("src/") for path in _BOOTSTRAP_JSON_ASSETS)


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


def _python_release_version(repo_root: Path) -> str:
    package_json = json.loads((repo_root / "package.json").read_text(encoding="utf-8"))
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))

    package_version = str(package_json["version"])
    python_version = str(package_json["gpdPythonVersion"])
    pyproject_version = str(pyproject["project"]["version"])

    assert package_version == python_version == pyproject_version
    return pyproject_version


def _npm_or_skip() -> str:
    npm = shutil.which("npm")
    if npm is None:
        pytest.skip("npm is not available")
    return npm


def _git_or_skip() -> str:
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not available")
    return git


def _npm_pack_dry_run(repo_root: Path, work_dir: Path) -> dict[str, object]:
    npm = _npm_or_skip()

    cache_dir = work_dir / "npm-cache"
    env = os.environ.copy()
    env.update(
        {
            "npm_config_audit": "false",
            "npm_config_cache": str(cache_dir),
            "npm_config_fund": "false",
            "npm_config_update_notifier": "false",
        }
    )

    result = subprocess.run(
        [npm, "pack", "--dry-run", "--json"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout

    pack_data = json.loads(result.stdout)
    assert isinstance(pack_data, list) and len(pack_data) == 1
    pack = pack_data[0]
    assert isinstance(pack, dict)
    return pack


def _repo_cache_snapshot(cache_root: Path) -> list[str]:
    transient_prefix = "__gpd_repo_graph_test__/"
    return sorted(
        rel_path
        for rel_path in (
            path.relative_to(cache_root).as_posix()
            for path in cache_root.rglob("*")
        )
        if rel_path != "__gpd_repo_graph_test__" and not rel_path.startswith(transient_prefix)
    )


def _packaged_file_paths(pack: dict[str, object]) -> set[str]:
    files = pack.get("files", [])
    assert isinstance(files, list)
    paths: set[str] = set()
    for entry in files:
        assert isinstance(entry, dict)
        path = entry.get("path")
        assert isinstance(path, str)
        paths.add(path)
    return paths


def _copy_release_surfaces(repo_root: Path, out_dir: Path) -> None:
    for relative_path in ("CHANGELOG.md", "CITATION.cff", "README.md", "package.json", "pyproject.toml"):
        shutil.copy2(repo_root / relative_path, out_dir / relative_path)


def _init_temp_git_repo(repo_dir: Path) -> None:
    _git_or_skip()
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_dir, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo_dir, check=True, capture_output=True,
    )


def _commit_in_temp_git_repo(repo_dir: Path, *, message: str, tracked_path: str, content: str) -> str:
    path = repo_dir / tracked_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", tracked_path], cwd=repo_dir, check=True, capture_output=True)

    message_path = repo_dir / ".git" / "COMMIT_EDITMSG"
    message_path.write_text(message, encoding="utf-8")
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "--file", str(message_path)],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _run_human_author_range_check(repo_dir: Path, git_range: str) -> subprocess.CompletedProcess[str]:
    hook_script = _repo_root() / "scripts" / "check-human-authors.sh"
    return subprocess.run(
        [str(hook_script), "--range", git_range],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=False,
    )


def _expected_runtime_dependency_names() -> set[str]:
    return {
        "jinja2",
        "mcp",
        "pillow",
        "pybtex",
        "pydantic",
        "pyyaml",
        "rich",
        "typer",
    }


def _expected_wheel_dependency_names() -> set[str]:
    return _expected_runtime_dependency_names() | {"arxiv-mcp-server"}


def _normalized_requirement_name(requirement: str) -> str:
    normalized: list[str] = []
    for char in requirement.split(";", 1)[0].strip():
        if char.isalnum() or char in {"-", "_", "."}:
            normalized.append(char)
            continue
        break
    return "".join(normalized).lower().replace("_", "-")


def _normalized_dependency_names(requirements: list[str]) -> set[str]:
    return {_normalized_requirement_name(requirement) for requirement in requirements}


def _wheel_dependency_names(metadata: str) -> set[str]:
    requirements = [
        line.split(":", 1)[1].strip()
        for line in metadata.splitlines()
        if line.startswith("Requires-Dist:")
    ]
    return _normalized_dependency_names(requirements)


def test_required_public_release_artifacts_exist() -> None:
    repo_root = _repo_root()
    required = (
        "README.md",
        "LICENSE",
        "CITATION.cff",
        "CONTRIBUTING.md",
        "package.json",
        "pyproject.toml",
    )

    missing = [path for path in required if not (repo_root / path).is_file()]
    assert missing == []


def test_changelog_vnext_bullets_are_unique() -> None:
    changelog = (_repo_root() / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(r"^## vNEXT\s*\n(.*?)(?=^## v|\Z)", changelog, re.M | re.S)
    assert match is not None, "Missing ## vNEXT section in CHANGELOG.md"

    bullets = [stripped for line in match.group(1).splitlines() if (stripped := line.strip()).startswith("- ")]
    assert len(bullets) == len(set(bullets))


def test_public_citation_metadata_uses_iso_release_date() -> None:
    repo_root = _repo_root()
    citation = (repo_root / "CITATION.cff").read_text(encoding="utf-8")

    assert re.search(r"^date-released: '\d{4}-\d{2}-\d{2}'$", citation, re.M)


def test_public_citation_and_readme_versions_match_release_version() -> None:
    repo_root = _repo_root()
    version = _python_release_version(repo_root)
    citation = (repo_root / "CITATION.cff").read_text(encoding="utf-8")
    readme = (repo_root / "README.md").read_text(encoding="utf-8")

    assert f"version: {version}" in citation
    assert f"version = {{{version}}}" in readme
    assert f"(Version {version})" in readme


def test_public_readme_citation_year_matches_citation_release_date() -> None:
    repo_root = _repo_root()
    citation = (repo_root / "CITATION.cff").read_text(encoding="utf-8")
    readme = (repo_root / "README.md").read_text(encoding="utf-8")

    match = re.search(r"^date-released: '(\d{4})-\d{2}-\d{2}'$", citation, re.M)
    assert match is not None
    release_year = match.group(1)

    assert f"year = {{{release_year}}}" in readme
    assert f"Physical Superintelligence PBC ({release_year}). Get Physics Done (GPD)" in readme


def test_public_metadata_records_psi_affiliation() -> None:
    repo_root = _repo_root()

    citation = (repo_root / "CITATION.cff").read_text(encoding="utf-8")
    contributing = (repo_root / "CONTRIBUTING.md").read_text(encoding="utf-8")
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))

    assert 'affiliation: "Physical Superintelligence PBC"' in citation
    assert "Physical Superintelligence PBC (PSI)" in contributing
    assert pyproject["project"]["authors"] == [{"name": "Physical Superintelligence PBC"}]
    assert pyproject["project"]["maintainers"] == [{"name": "Physical Superintelligence PBC"}]

def test_public_release_surfaces_share_agentic_system_positioning() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    package_json = json.loads((repo_root / "package.json").read_text(encoding="utf-8"))
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    installer = (repo_root / "bin" / "install.js").read_text(encoding="utf-8")

    expected = "open-source agentic ai system for physics research"
    assert expected in readme.lower()
    assert expected in package_json["description"].lower()
    assert expected in pyproject["project"]["description"].lower()
    assert "Open-source agentic AI system for physics research" in installer


def test_pyproject_wheel_targets_real_gpd_package() -> None:
    repo_root = _repo_root()
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]

    assert wheel["packages"] == ["gpd"]
    assert wheel["package-dir"] == {"": "src"}


def test_pyproject_wheel_artifacts_match_source_assets() -> None:
    repo_root = _repo_root()
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]
    artifacts = wheel["artifacts"]

    assert isinstance(artifacts, list)
    assert artifacts

    seen: set[str] = set()
    for pattern in artifacts:
        assert isinstance(pattern, str)
        assert pattern.startswith("src/gpd/"), f"Wheel artifact {pattern!r} must live under src/gpd"
        assert pattern not in seen, f"Wheel artifact list contains duplicate pattern {pattern!r}"
        seen.add(pattern)

        matches = [path for path in repo_root.glob(pattern) if path.is_file()]
        assert matches, f"Wheel artifact pattern {pattern!r} matches no files"
        for matched in matches:
            relative = matched.relative_to(repo_root)
            assert str(relative).startswith("src/gpd/"), "Matched file is outside src/gpd"


def test_public_bootstrap_package_exposes_npx_installer() -> None:
    repo_root = _repo_root()
    package_json = json.loads((repo_root / "package.json").read_text(encoding="utf-8"))
    packaged_files = set(package_json.get("files", []))

    assert package_json["name"] == "get-physics-done"
    assert package_json.get("bin", {}).get("get-physics-done") == "bin/install.js"
    assert "bin/install.js" in packaged_files
    assert set(_BOOTSTRAP_JSON_ASSETS) <= packaged_files
    assert (repo_root / "bin" / "install.js").is_file()


def test_wheel_package_includes_runtime_json_assets_needed_at_import_time() -> None:
    repo_root = _repo_root()
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))

    force_include = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    assert force_include == dict(zip(_BOOTSTRAP_JSON_ASSETS, _WHEEL_JSON_ASSETS, strict=True))


def test_npm_files_match_bootstrap_installer_resource_strategy() -> None:
    repo_root = _repo_root()
    package_json = json.loads((repo_root / "package.json").read_text(encoding="utf-8"))
    installer = (repo_root / "bin" / "install.js").read_text(encoding="utf-8")
    packaged_files = set(package_json.get("files", []))
    required_requires = {
        "src/gpd/adapters/runtime_catalog.json": 'require("../src/gpd/adapters/runtime_catalog.json")',
        "src/gpd/adapters/runtime_catalog_schema.json": 'require("../src/gpd/adapters/runtime_catalog_schema.json")',
        "src/gpd/core/public_surface_contract.json": 'require("../src/gpd/core/public_surface_contract.json")',
        "src/gpd/core/public_surface_contract_schema.json": (
            'require("../src/gpd/core/public_surface_contract_schema.json")'
        ),
    }

    assert "bin/install.js" in packaged_files
    assert set(required_requires) <= packaged_files
    for expected_require in required_requires.values():
        assert expected_require in installer


def test_public_bootstrap_installer_uses_python_cli_without_uv() -> None:
    repo_root = _repo_root()
    content = (repo_root / "bin" / "install.js").read_text(encoding="utf-8")

    assert "uv" not in content
    assert "gpd.cli" in content


def test_public_bootstrap_installer_pins_the_matching_python_release() -> None:
    repo_root = _repo_root()
    content = (repo_root / "bin" / "install.js").read_text(encoding="utf-8")

    assert 'require("../package.json")' in content
    assert 'require("../src/gpd/core/public_surface_contract.json")' in content
    assert 'require("../src/gpd/core/public_surface_contract_schema.json")' in content
    assert "gpdPythonVersion" in content
    assert '["-m", "venv", "--help"]' in content
    assert "managed environment" in content
    assert 'const GITHUB_MAIN_BRANCH = "main"' in content
    assert 'const MAIN_BRANCH_UPGRADE_ENV = "GPD_BOOTSTRAP_ENABLE_MAIN_BRANCH_UPGRADE"' in content
    assert "installManagedPackage(managedEnv.python, pythonPackageVersion" in content
    assert 'process.env[MAIN_BRANCH_UPGRADE_ENV] !== "1"' in content
    assert "Skipping GitHub ${GITHUB_MAIN_BRANCH} upgrade because ${MAIN_BRANCH_UPGRADE_ENV}=1 is not set." in content
    assert "archive/refs/tags/v${version}.tar.gz" in content
    assert "archive/refs/heads/${GITHUB_MAIN_BRANCH}.tar.gz" in content
    assert "git+${repoGitUrl}@v${version}" in content
    assert "git+${repoGitUrl}@${GITHUB_MAIN_BRANCH}" in content
    assert "function repositoryGitUrl(" in content
    assert "function repositorySshGitUrl(" not in content
    assert "requestedVersion" in content
    assert "GitHub sources" in content


def test_public_bootstrap_installer_requires_runtime_catalog_assets() -> None:
    repo_root = _repo_root()
    content = (repo_root / "bin" / "install.js").read_text(encoding="utf-8")

    assert 'require("../src/gpd/adapters/runtime_catalog.json")' in content
    assert 'require("../src/gpd/adapters/runtime_catalog_schema.json")' in content


def test_export_workflow_uses_release_attribution_footer() -> None:
    repo_root = _repo_root()
    content = (repo_root / "src" / "gpd" / "specs" / "workflows" / "export.md").read_text(encoding="utf-8")

    assert "<p><em>Generated with Get Physics Done (PSI)" in content
    assert "{\\footnotesize\\textit{Generated with Get Physics Done (PSI)}}" in content
    assert "Attribution: Generated with Get Physics Done (PSI)" in content
    assert "Tool: GPD (Get Physics Done)" not in content


def test_export_surfaces_use_visible_exports_directory() -> None:
    repo_root = _repo_root()
    workflow = (repo_root / "src" / "gpd" / "specs" / "workflows" / "export.md").read_text(encoding="utf-8")
    command = (repo_root / "src" / "gpd" / "commands" / "export.md").read_text(encoding="utf-8")

    assert "mkdir -p exports" in workflow
    assert "exports/results.html" in workflow
    assert "exports/results.tex" in workflow
    assert "exports/results.bib" in workflow
    assert "exports/results.zip" in workflow
    assert "GPD/exports" not in workflow
    assert "Write files to `exports/`." in command
    assert "Files written to exports/" in command
    assert "GPD/exports" not in command


def test_public_cli_surface_is_unified() -> None:
    repo_root = _repo_root()
    script_lines = _project_script_lines(repo_root)
    script_names = [line.split("=", 1)[0].strip().strip('"') for line in script_lines]

    assert 'gpd = "gpd.cli:entrypoint"' in script_lines
    assert all(name == "gpd" or name.startswith("gpd-mcp-") for name in script_names)
    assert sorted(path.name for path in (repo_root / "src" / "gpd").glob("cli*.py")) == ["cli.py"]


def test_project_script_targets_are_importable() -> None:
    repo_root = _repo_root()
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))

    for script_name, target in pyproject["project"]["scripts"].items():
        module_name, separator, attribute_name = target.partition(":")
        assert separator == ":", f"{script_name} must use module:attribute syntax"
        assert getattr(import_module(module_name), attribute_name, None) is not None


def test_packaged_resource_directories_and_hooks_are_importable() -> None:
    required_resource_dirs = ("agents", "commands", "specs")
    for resource_dir in required_resource_dirs:
        assert resources.files("gpd").joinpath(resource_dir).is_dir()

    hook_modules = {path.removesuffix(".py") for path in HOOK_SCRIPTS.values()}
    assert {path.rsplit("/", 1)[-1].removesuffix(".py") for path in bundled_hook_relpaths()} >= hook_modules
    for module_name in hook_modules:
        assert import_module(f"gpd.hooks.{module_name}") is not None


def test_merge_gate_workflow_uses_main_branch_pytest_on_python_311() -> None:
    repo_root = _repo_root()
    workflow = (repo_root / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")

    assert "name: tests" in workflow
    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert "branches: [main]" in workflow
    assert "workflow_dispatch:" in workflow
    assert "name: pytest ${{ matrix.display_name }} (3.11)" in workflow
    assert "fail-fast: false" in workflow
    assert "display_name: root 1/9" in workflow
    assert "display_name: root 9/9" in workflow
    assert "display_name: adapters 1/2" in workflow
    assert "display_name: adapters 2/2" in workflow
    assert "display_name: hooks 1/2" in workflow
    assert "display_name: hooks 2/2" in workflow
    assert "display_name: mcp" in workflow
    assert "display_name: core 5/5" in workflow
    assert "actions/checkout@v6" in workflow
    assert "actions/setup-python@v6" in workflow
    assert 'python-version: "3.11"' in workflow
    assert "astral-sh/setup-uv@v7" in workflow
    assert "uv sync --dev" in workflow
    assert 'addopts = "-n auto --dist=worksteal"' in pyproject
    assert "plan-shards:" in workflow
    assert "Plan pytest shards" in workflow
    assert "Upload pytest shard plan" in workflow
    assert "Download pytest shard plan" in workflow
    assert "Run pytest shard" in workflow
    assert "from tests.ci_sharding import write_ci_shard_plan" in workflow
    assert "PYTEST_SHARD_PLAN_DIR" in workflow
    assert "pytest-shard-plan" in workflow
    assert 'uv run pytest -q --durations=20 --durations-min=0 "${PYTEST_TARGETS[@]}"' in workflow


def test_staging_rebuild_workflow_stays_separate_and_dispatches_the_tested_main_push_sha() -> None:
    repo_root = _repo_root()
    tests_workflow = (repo_root / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
    rebuild_workflow = (repo_root / ".github" / "workflows" / "staging-rebuild.yml").read_text(
        encoding="utf-8"
    )
    normalized_rebuild_workflow = rebuild_workflow.replace('\\"', '"')

    assert "trigger-staging-rebuild" not in tests_workflow
    assert "gpd-web/dispatches" not in tests_workflow

    assert "name: staging rebuild" in rebuild_workflow
    assert "workflow_run:" in rebuild_workflow
    assert 'workflows: ["tests"]' in rebuild_workflow
    assert "types: [completed]" in rebuild_workflow
    assert "branches: [main]" in rebuild_workflow
    assert "workflow_run.conclusion == 'success'" in rebuild_workflow
    assert "workflow_run.event == 'push'" in rebuild_workflow

    assert "repos/physicalsuperintelligence/gpd-web/dispatches" in rebuild_workflow
    assert '"event_type":"rebuild-gpd"' in normalized_rebuild_workflow
    assert '"source":"github"' in normalized_rebuild_workflow
    assert '"repo":"psi-oss/get-physics-done"' in normalized_rebuild_workflow
    assert '"version":"${{ github.event.workflow_run.head_sha }}"' in normalized_rebuild_workflow
    assert '"version":"${{ github.sha }}"' not in normalized_rebuild_workflow
    assert '"version":"main"' not in normalized_rebuild_workflow
    assert '"image_tag":"staging"' in normalized_rebuild_workflow
    assert "GPD_WEB_DISPATCH_TOKEN not configured" in rebuild_workflow


def test_prepare_release_workflow_creates_release_pr_without_publishing() -> None:
    repo_root = _repo_root()
    workflow = (repo_root / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert "Admin-owned release workflow:" in workflow
    assert "This workflow never publishes anything and never pushes to `main`." in workflow
    assert "opens a release PR on `release/vX.Y.Z`." in workflow
    assert "name: prepare release" in workflow
    assert "workflow_dispatch:" in workflow
    assert 'description: "Dry run — validate and preview without opening a release PR"' in workflow
    assert "pull-requests: write" in workflow
    assert "actions/checkout@v6" in workflow
    assert "actions/setup-python@v6" in workflow
    assert "actions/setup-node@v6" in workflow
    assert "astral-sh/setup-uv@v7" in workflow
    assert "uv sync --dev --frozen" in workflow
    assert "scripts/release_workflow.py prepare" in workflow
    assert "uv run pytest tests/test_release_consistency.py -v" in workflow
    assert "uv build" in workflow
    assert "npm pack --dry-run --json" in workflow
    assert "gh pr create" in workflow
    assert 'git add CHANGELOG.md CITATION.cff README.md package.json pyproject.toml' in workflow
    assert "Publish release" in workflow
    assert "pypa/gh-action-pypi-publish@release/v1" not in workflow
    assert "npm publish" not in workflow
    assert "gh release create" not in workflow


def test_publish_release_workflow_uses_trusted_publishing_from_merged_release_commit() -> None:
    repo_root = _repo_root()
    workflow = (repo_root / ".github" / "workflows" / "publish-release.yml").read_text(encoding="utf-8")

    assert "Admin-owned publish workflow:" in workflow
    assert "Run manually from merged `main` after the release PR has landed." in workflow
    assert "Ordinary PR merges to `main` must never invoke this flow automatically." in workflow
    assert "name: publish release" in workflow
    assert "workflow_dispatch:" in workflow
    assert "scripts/release_workflow.py show-version" in workflow
    assert "scripts/release_workflow.py stamp-publish-date" in workflow
    assert re.search(
        r'^\s*python scripts/release_workflow\.py stamp-publish-date --repo \. --release-date "\$\{\{ needs\.build-release\.outputs\.release_date \}\}" > /tmp/publish-date\.json$',
        workflow,
        re.M,
    )
    assert not re.search(
        r'^\s*uv run python scripts/release_workflow\.py stamp-publish-date --repo \. --release-date "\$\{\{ needs\.build-release\.outputs\.release_date \}\}" > /tmp/publish-date\.json$',
        workflow,
        re.M,
    )
    assert "environment:" in workflow
    assert "name: PyPI" in workflow
    assert "id-token: write" in workflow
    assert "actions/checkout@v6" in workflow
    assert "actions/setup-python@v6" in workflow
    assert "actions/setup-node@v6" in workflow
    assert "actions/upload-artifact@v7" in workflow
    assert "actions/download-artifact@v8" in workflow
    assert "pypa/gh-action-pypi-publish@release/v1" in workflow
    assert "npm publish" in workflow
    assert "gh release create" in workflow
    assert "post-release/v${VERSION}-publish-date" in workflow
    assert "ref: ${{ needs.build-release.outputs.release_sha }}" in workflow
    assert "scripts/release_workflow.py release-notes" in workflow
    assert re.search(
        r'^\s*python scripts/release_workflow\.py release-notes --repo \. --version "\$VERSION" > /tmp/release-notes\.txt$',
        workflow,
        re.M,
    )
    assert not re.search(
        r'^\s*uv run python scripts/release_workflow\.py release-notes --repo \. --version "\$VERSION" > /tmp/release-notes\.txt$',
        workflow,
        re.M,
    )
    assert "gh pr create" in workflow


def test_claude_sdk_is_not_shipped_in_public_install() -> None:
    repo_root = _repo_root()
    project = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    dependencies: list[str] = project["dependencies"]
    optional = project.get("optional-dependencies", {})

    assert not any(item.startswith("claude-agent-sdk") for item in dependencies)
    assert "claude-subagents" not in optional
    assert not any(
        item.startswith("claude-agent-sdk") for items in optional.values() for item in items
    )
    assert "scientific" not in optional


def test_public_runtime_dependency_surface_stays_curated() -> None:
    repo_root = _repo_root()
    project = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    dependencies: list[str] = project["dependencies"]
    optional = project.get("optional-dependencies", {})

    assert _normalized_dependency_names(dependencies) == _expected_runtime_dependency_names()
    assert optional == {"arxiv": ["arxiv-mcp-server>=0.4.11"]}





def test_infra_descriptors_reference_public_bootstrap_flow() -> None:
    from gpd.mcp.builtin_servers import build_public_descriptors

    repo_root = _repo_root()
    expected = "Install GPD before enabling built-in MCP servers."
    stale_markers = (
        "packages/gpd",
        "uv pip install -e",
        "pip install -e packages/gpd",
        _SHARED_INSTALL.bootstrap_command,
    )
    expected_descriptors = build_public_descriptors()

    for path in sorted((repo_root / "infra").glob("gpd-*.json")):
        content = path.read_text(encoding="utf-8")
        assert expected in content, f"{path.name} should reference the public prerequisite flow"
        for marker in stale_markers:
            assert marker not in content, f"{path.name} should not mention {marker!r}"
        descriptor = json.loads(content)
        descriptor.pop("source_of_truth", None)
        assert descriptor == expected_descriptors[path.stem]

    assert {
        path.stem for path in (repo_root / "infra").glob("gpd-*.json")
    } == set(expected_descriptors)


def test_public_gpd_infra_descriptors_use_entry_points_not_python() -> None:
    repo_root = _repo_root()

    for path in sorted((repo_root / "infra").glob("gpd-*.json")):
        descriptor = json.loads(path.read_text(encoding="utf-8"))
        assert descriptor["command"].startswith("gpd-mcp-")
        assert descriptor["args"] == []


def test_gitignore_covers_repo_local_npm_cache() -> None:
    repo_root = _repo_root()
    assert ".npm-cache/" in (repo_root / ".gitignore").read_text(encoding="utf-8")


def test_gitignore_covers_repo_local_tmp_root() -> None:
    repo_root = _repo_root()
    content = (repo_root / ".gitignore").read_text(encoding="utf-8")

    assert "tmp/" in content


def test_gitignore_does_not_exclude_gpd_directory() -> None:
    """Regression: GPD/ must not be gitignored.

    Workflow commit commands (``gpd commit``) include GPD/ files; gitignoring
    them causes ``git add`` failures.  A pre-commit hook strips GPD/ from
    commits to the codebase repo instead.
    """
    repo_root = _repo_root()
    content = (repo_root / ".gitignore").read_text(encoding="utf-8")
    for pattern in ("GPD/", "GPD/*", "GPD/STATE.md", "GPD/state.json", "GPD/state.json.bak"):
        assert pattern not in content, f".gitignore must not contain {pattern!r}"


def test_pre_commit_config_blocks_gpd_directory() -> None:
    """The pre-commit config must include the block-gpd-directory hook."""
    import yaml

    repo_root = _repo_root()
    config = yaml.safe_load((repo_root / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hook_ids = [h["id"] for repo in config["repos"] for h in repo["hooks"]]
    assert "block-gpd-directory" in hook_ids


def test_block_gpd_commit_hook_script_exists_and_is_executable() -> None:
    repo_root = _repo_root()
    hook_script = repo_root / "scripts" / "block-gpd-commit.sh"
    assert hook_script.exists(), "scripts/block-gpd-commit.sh must exist"
    assert os.access(hook_script, os.X_OK), "scripts/block-gpd-commit.sh must be executable"


@pytest.mark.skipif(os.name == "nt", reason="requires bash")
def test_block_gpd_commit_hook_unstages_gpd_files(tmp_path: Path) -> None:
    """Integration: the hook script strips GPD/ files from the index."""
    _git_or_skip()
    repo_root = _repo_root()
    hook_script = repo_root / "scripts" / "block-gpd-commit.sh"

    # Set up a throwaway git repo.
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path, check=True, capture_output=True,
    )

    # Seed an initial commit so HEAD exists.
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path, check=True, capture_output=True,
    )

    # Stage a GPD file and a non-GPD file.
    gpd_dir = tmp_path / "GPD"
    gpd_dir.mkdir()
    (gpd_dir / "STATE.md").write_text("state\n", encoding="utf-8")
    (tmp_path / "real.txt").write_text("real\n", encoding="utf-8")
    subprocess.run(["git", "add", "GPD/STATE.md", "real.txt"], cwd=tmp_path, check=True, capture_output=True)

    # Run the hook script.
    result = subprocess.run(
        [str(hook_script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0

    # GPD/STATE.md should be unstaged; real.txt should remain staged.
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=tmp_path, capture_output=True, text=True, check=True,
    )
    staged_files = staged.stdout.strip().splitlines()
    assert "real.txt" in staged_files
    assert "GPD/STATE.md" not in staged_files


@pytest.mark.skipif(os.name == "nt", reason="requires sh")
def test_human_author_hook_blocks_non_human_coauthors(tmp_path: Path) -> None:
    repo_root = _repo_root()
    hook_script = repo_root / "scripts" / "check-human-authors.sh"
    message = tmp_path / "COMMIT_EDITMSG"
    message.write_text("Improve tests\n\nCo-Authored-By: GPT <noreply@openai.com>\n", encoding="utf-8")

    result = subprocess.run([str(hook_script), str(message)], capture_output=True, text=True, check=False)

    assert result.returncode == 1
    assert "non-human co-author detected" in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="requires sh")
def test_human_author_hook_allows_human_coauthors(tmp_path: Path) -> None:
    repo_root = _repo_root()
    hook_script = repo_root / "scripts" / "check-human-authors.sh"
    message = tmp_path / "COMMIT_EDITMSG"
    message.write_text("Improve tests\n\nCo-Authored-By: Ada Lovelace <ada@example.com>\n", encoding="utf-8")

    result = subprocess.run([str(hook_script), str(message)], capture_output=True, text=True, check=False)

    assert result.returncode == 0


@pytest.mark.skipif(os.name == "nt", reason="requires sh")
def test_human_author_range_check_blocks_non_human_coauthors_on_head_commit(tmp_path: Path) -> None:
    _init_temp_git_repo(tmp_path)
    _commit_in_temp_git_repo(tmp_path, message="init\n", tracked_path="README.md", content="seed\n")
    offending_hash = _commit_in_temp_git_repo(
        tmp_path,
        message="Improve tests\n\nCo-Authored-By: GPT <noreply@openai.com>\n",
        tracked_path="README.md",
        content="seed\nhead\n",
    )

    result = _run_human_author_range_check(tmp_path, "HEAD^!")

    assert result.returncode == 1
    assert "non-human co-author lines found in commit range HEAD^!" in result.stderr
    assert offending_hash in result.stderr
    assert "Improve tests" in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="requires sh")
def test_human_author_range_check_handles_root_commit(tmp_path: Path) -> None:
    _init_temp_git_repo(tmp_path)
    root_hash = _commit_in_temp_git_repo(
        tmp_path,
        message="Initial import\n\nCo-Authored-By: GPT <noreply@openai.com>\n",
        tracked_path="README.md",
        content="seed\n",
    )

    result = _run_human_author_range_check(tmp_path, "HEAD^!")

    assert result.returncode == 1
    assert "non-human co-author lines found in commit range HEAD^!" in result.stderr
    assert root_hash in result.stderr
    assert "Initial import" in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="requires sh")
def test_human_author_range_check_rejects_invalid_range(tmp_path: Path) -> None:
    _init_temp_git_repo(tmp_path)
    _commit_in_temp_git_repo(tmp_path, message="init\n", tracked_path="README.md", content="seed\n")

    result = _run_human_author_range_check(tmp_path, "definitely-not-a-rev..HEAD")

    assert result.returncode == 1
    assert "invalid git range definitely-not-a-rev..HEAD" in result.stderr
    assert "Human author attribution check passed" not in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="requires sh")
def test_human_author_range_check_is_case_insensitive(tmp_path: Path) -> None:
    _init_temp_git_repo(tmp_path)
    _commit_in_temp_git_repo(tmp_path, message="init\n", tracked_path="README.md", content="seed\n")
    offending_hash = _commit_in_temp_git_repo(
        tmp_path,
        message="Improve tests\n\nco-authored-by: GPT <noreply@openai.com>\n",
        tracked_path="README.md",
        content="seed\nlowercase\n",
    )

    result = _run_human_author_range_check(tmp_path, "HEAD^!")

    assert result.returncode == 1
    assert offending_hash in result.stderr
    assert "Improve tests" in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="requires sh")
def test_human_author_range_check_scans_full_multi_commit_ranges(tmp_path: Path) -> None:
    _init_temp_git_repo(tmp_path)
    _commit_in_temp_git_repo(tmp_path, message="Base commit\n", tracked_path="README.md", content="seed\n")
    bad_middle_hash = _commit_in_temp_git_repo(
        tmp_path,
        message="Bad middle\n\nCo-Authored-By: GPT <noreply@openai.com>\n",
        tracked_path="README.md",
        content="seed\nmiddle\n",
    )
    good_tip_hash = _commit_in_temp_git_repo(
        tmp_path,
        message="Good tip\n\nCo-Authored-By: Ada Lovelace <ada@example.com>\n",
        tracked_path="README.md",
        content="seed\nmiddle\ntip\n",
    )

    result = _run_human_author_range_check(tmp_path, "HEAD~2..HEAD")

    assert result.returncode == 1
    assert bad_middle_hash in result.stderr
    assert "Bad middle" in result.stderr
    assert good_tip_hash not in result.stderr
    assert "Good tip" not in result.stderr


def test_npm_pack_dry_run_uses_temp_cache_outside_repo(tmp_path: Path) -> None:
    repo_root = _repo_root()
    _npm_or_skip()

    repo_cache = repo_root / ".npm-cache"
    existed_before = repo_cache.exists()
    before_paths = _repo_cache_snapshot(repo_cache) if existed_before else []

    pack = _npm_pack_dry_run(repo_root, tmp_path)
    packed_paths = _packaged_file_paths(pack)

    assert pack["name"] == "get-physics-done"
    assert pack["version"] == _python_release_version(repo_root)
    assert "bin/install.js" in packed_paths
    assert "package.json" in packed_paths
    assert set(_BOOTSTRAP_JSON_ASSETS) <= packed_paths
    assert (tmp_path / "npm-cache").is_dir()

    if existed_before:
        after_paths = _repo_cache_snapshot(repo_cache)
        assert after_paths == before_paths
    else:
        assert not repo_cache.exists()



def test_prepare_release_updates_all_versioned_public_surfaces(tmp_path: Path) -> None:
    repo_root = _repo_root()
    _copy_release_surfaces(repo_root, tmp_path)
    current_version = _python_release_version(repo_root)
    next_version = bump_version(current_version, "patch")
    original_citation = (tmp_path / "CITATION.cff").read_text(encoding="utf-8")
    original_readme = (tmp_path / "README.md").read_text(encoding="utf-8")

    changelog_path = tmp_path / "CHANGELOG.md"
    changelog_path.write_text(
        (repo_root / "CHANGELOG.md").read_text(encoding="utf-8").replace(
            "All notable changes to Get Physics Done are documented here.\n\n",
            "All notable changes to Get Physics Done are documented here.\n\n"
            "## vNEXT\n\n"
            "- Manual release workflows now prepare a release PR and publish only after an explicit publish action.\n\n",
            1,
        ),
        encoding="utf-8",
    )

    metadata = prepare_release(tmp_path, "patch")

    assert metadata.previous_version == current_version
    assert metadata.version == next_version
    assert metadata.release_branch == f"release/v{next_version}"
    assert metadata.release_notes.startswith("- Manual release workflows now prepare")

    assert f'version = "{next_version}"' in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    package_json = json.loads((tmp_path / "package.json").read_text(encoding="utf-8"))
    assert package_json["version"] == next_version
    assert package_json["gpdPythonVersion"] == next_version

    citation = (tmp_path / "CITATION.cff").read_text(encoding="utf-8")
    assert f"version: {next_version}" in citation
    assert citation == original_citation.replace(f"version: {current_version}", f"version: {next_version}")

    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert f"version = {{{next_version}}}" in readme
    assert f"(Version {next_version})" in readme
    assert "year = {2026}" in readme
    assert readme == original_readme.replace(f"version = {{{current_version}}}", f"version = {{{next_version}}}").replace(
        f"(Version {current_version})",
        f"(Version {next_version})",
    )

    changelog = changelog_path.read_text(encoding="utf-8")
    assert changelog.startswith(
        "# Changelog\n\nAll notable changes to Get Physics Done are documented here.\n\n"
        f"## vNEXT\n\n## v{next_version}\n"
    )
    assert extract_release_notes(changelog, next_version) == metadata.release_notes


def test_prepare_release_requires_nonempty_vnext_section(tmp_path: Path) -> None:
    repo_root = _repo_root()
    _copy_release_surfaces(repo_root, tmp_path)
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## v1.1.0\n\n- Existing release notes.\n", encoding="utf-8")

    with pytest.raises(ReleaseError, match="No ## vNEXT section found"):
        prepare_release(tmp_path, "patch")

    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## vNEXT\n\n", encoding="utf-8")

    with pytest.raises(ReleaseError, match="## vNEXT section in CHANGELOG.md is empty"):
        prepare_release(tmp_path, "patch")


def test_stamp_publish_date_updates_citation_release_date_and_readme_year(tmp_path: Path) -> None:
    repo_root = _repo_root()
    _copy_release_surfaces(repo_root, tmp_path)

    metadata = stamp_publish_date(tmp_path, release_date="2027-01-02")

    assert metadata.release_date == "2027-01-02"
    assert metadata.release_year == "2027"
    assert metadata.changed_files == ("CITATION.cff", "README.md")

    citation = (tmp_path / "CITATION.cff").read_text(encoding="utf-8")
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "date-released: '2027-01-02'" in citation
    assert "year = {2027}" in readme
    assert "Physical Superintelligence PBC (2027). Get Physics Done (GPD)" in readme


def test_stamp_publish_date_reports_no_changes_when_release_date_already_matches(tmp_path: Path) -> None:
    repo_root = _repo_root()
    _copy_release_surfaces(repo_root, tmp_path)

    metadata = stamp_publish_date(tmp_path, release_date="2026-03-15")

    assert metadata.changed_files == ()


def test_stamp_publish_date_rejects_full_datetime_release_inputs(tmp_path: Path) -> None:
    repo_root = _repo_root()
    _copy_release_surfaces(repo_root, tmp_path)

    with pytest.raises(ReleaseError, match="YYYY-MM-DD"):
        stamp_publish_date(tmp_path, release_date="2026-03-15T12:34:56Z")
