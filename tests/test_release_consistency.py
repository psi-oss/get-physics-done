"""Guardrails for public release consistency."""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest
import yaml

from gpd._python_compat import MIN_SUPPORTED_PYTHON_LABEL
from gpd.adapters.runtime_catalog import get_shared_install_metadata, iter_runtime_descriptors
from scripts.release_workflow import (
    ReleaseError,
    bump_version,
    extract_release_notes,
    prepare_release,
    stamp_publish_date,
    update_readme_version_text,
)
from tests.ci_sharding import assert_ci_workflow_pytest_shard_policy


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


_SHARED_INSTALL = get_shared_install_metadata()
_BOOTSTRAP_JSON_ASSETS = (
    "src/gpd/adapters/runtime_catalog.json",
    "src/gpd/adapters/runtime_catalog_schema.json",
    "src/gpd/core/public_surface_contract.json",
    "src/gpd/core/public_surface_contract_schema.json",
)
_EXPECTED_OPTIONAL_DEPENDENCIES = {
    "paper": ["cairosvg>=2.7.0", "pypdf>=5.0"],
    "arxiv": ["arxiv-mcp-server>=0.4.11", "arxiv>=2.4.1", "cairosvg>=2.7.0", "pypdf>=5.0"],
}
_OPTIONAL_DECLARED_PUBLICATION_IMPORTS = {
    "src/gpd/mcp/paper/bibliography.py": {"arxiv"},
    "src/gpd/mcp/paper/figures.py": {"cairosvg"},
}


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


def _uv_lock_project_version(repo_root: Path) -> str:
    lock = tomllib.loads((repo_root / "uv.lock").read_text(encoding="utf-8"))
    packages = lock.get("package", [])
    assert isinstance(packages, list)
    for package in packages:
        if not isinstance(package, dict):
            continue
        if package.get("name") == "get-physics-done" and package.get("source") == {"editable": "."}:
            return str(package["version"])
    raise AssertionError("uv.lock is missing the editable get-physics-done package entry")


def _npm_pack_dry_run(repo_root: Path, work_dir: Path) -> dict[str, object]:
    npm = shutil.which("npm")
    assert npm is not None, "npm is required for npm pack validation"

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


def _source_wheel_package_data_paths(src_gpd: Path) -> set[str]:
    package_root = src_gpd.parent
    required_roots = ("commands", "agents", "specs")
    package_data = {
        path.relative_to(package_root).as_posix()
        for root_name in required_roots
        for path in (src_gpd / root_name).rglob("*")
        if path.is_file()
    }
    package_data.update(
        path.relative_to(package_root).as_posix()
        for path in src_gpd.rglob("*")
        if path.is_file() and path.suffix in {".json", ".tex"}
    )
    return package_data


def _uv_build_blocked_by_environment(stderr: str) -> bool:
    """Detect uv failures that happen before the package build starts."""

    return (
        ("failed to open file" in stderr and "/.cache/uv/sdists" in stderr)
        or (
            "system-configuration" in stderr
            and "Attempted to create a NULL object" in stderr
            and "Tokio executor failed" in stderr
        )
    )


def _copy_checkout_for_release_test(repo_root: Path, destination: Path) -> None:
    shutil.copytree(
        repo_root,
        destination,
        ignore=shutil.ignore_patterns(
            ".git",
            ".mypy_cache",
            ".npm-cache",
            ".pytest_cache",
            ".ruff_cache",
            ".uv-cache",
            ".venv",
            "__pycache__",
            "*.egg-info",
            "*.pyc",
            "*.pyo",
            "build",
            "dist",
            "GPD*",
            "tmp",
        ),
    )


def _copy_release_surfaces(repo_root: Path, out_dir: Path) -> None:
    for relative_path in ("CHANGELOG.md", "CITATION.cff", "README.md", "package.json", "pyproject.toml"):
        shutil.copy2(repo_root / relative_path, out_dir / relative_path)


def _direct_imported_modules(repo_root: Path, relative_path: str) -> set[str]:
    tree = ast.parse((repo_root / relative_path).read_text(encoding="utf-8"), filename=relative_path)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".", 1)[0] for alias in node.names)
            continue
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".", 1)[0])
    return modules


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
    optional_requirements = [
        requirement
        for requirements in _EXPECTED_OPTIONAL_DEPENDENCIES.values()
        for requirement in requirements
    ]
    return _expected_runtime_dependency_names() | _normalized_dependency_names(optional_requirements)


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


def test_public_citation_metadata_uses_iso_release_date() -> None:
    repo_root = _repo_root()
    citation = (repo_root / "CITATION.cff").read_text(encoding="utf-8")

    assert re.search(r"^date-released: '\d{4}-\d{2}-\d{2}'$", citation, re.M)


def test_bug_report_template_asks_for_current_version_without_stale_placeholder() -> None:
    import yaml

    repo_root = _repo_root()
    template = yaml.safe_load((repo_root / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml").read_text(encoding="utf-8"))
    version_field = next(item for item in template["body"] if item.get("id") == "version")
    attributes = version_field["attributes"]

    assert "`gpd --version`" in attributes["description"]
    assert not re.search(r"\b\d+\.\d+\.\d+\b", attributes["placeholder"])


def test_public_citation_and_readme_versions_match_release_version() -> None:
    repo_root = _repo_root()
    version = _python_release_version(repo_root)
    citation = (repo_root / "CITATION.cff").read_text(encoding="utf-8")
    readme = (repo_root / "README.md").read_text(encoding="utf-8")

    assert f"version: {version}" in citation
    assert f"version = {{{version}}}" in readme
    assert f"(Version {version})" in readme


def test_uv_lock_matches_release_version() -> None:
    repo_root = _repo_root()
    assert _uv_lock_project_version(repo_root) == _python_release_version(repo_root)


def test_installed_prompt_sources_do_not_pin_release_version_literals() -> None:
    repo_root = _repo_root()
    version = _python_release_version(repo_root)

    offenders = [
        path.relative_to(repo_root).as_posix()
        for path in sorted((repo_root / "src" / "gpd").rglob("*"))
        if path.is_file() and path.suffix in {".md", ".py", ".json", ".toml", ".yaml", ".yml"}
        if version in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


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


def test_readme_exposes_pypi_and_npm_release_badges() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")

    assert "https://pypi.org/project/get-physics-done/" in readme
    assert "https://img.shields.io/pypi/v/get-physics-done" in readme
    assert "labelColor=3775a9&color=ffd43b" in readme
    assert "https://www.npmjs.com/package/get-physics-done" in readme
    assert "https://img.shields.io/npm/v/get-physics-done" in readme
    assert "labelColor=1f1f1f&color=cb3837" in readme


def test_readme_labels_prefixless_runtime_examples_as_canonical_command_names() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")

    assert "Canonical post-install order, shown as command names without runtime prefixes:" in readme
    assert "The table below uses canonical command names without runtime prefixes." in readme
    assert "Apply the\nprefix for your runtime from [Supported Runtimes](#supported-runtimes)." in readme


def test_public_codex_windows_docs_track_current_official_guidance() -> None:
    repo_root = _repo_root()
    codex = (repo_root / "docs" / "codex.md").read_text(encoding="utf-8")
    windows = (repo_root / "docs" / "windows.md").read_text(encoding="utf-8")
    combined = f"{codex}\n{windows}"

    assert "Windows support is\nexperimental" not in codex
    assert "Codex support on Windows is still experimental" not in windows
    assert "macOS, Windows, and Linux" in codex
    assert "macOS, Windows, and Linux" in windows
    assert "PowerShell" in codex
    assert "PowerShell" in windows
    assert "Windows sandbox" in codex
    assert "Windows sandbox" in windows
    assert "WSL2" in codex
    assert "WSL2" in windows
    assert combined.count("https://developers.openai.com/codex/windows") == 2


def test_pull_request_template_points_to_current_ci_and_pre_commit_validation() -> None:
    repo_root = _repo_root()
    template = (repo_root / ".github" / "pull_request_template.md").read_text(encoding="utf-8")

    assert "uv run pytest -v" not in template
    assert "ruff check src/ tests/" not in template
    assert "uv run pytest -q <targets>" in template
    assert "GitHub Actions PR checks" in template
    assert "uv run ruff check ." in template
    assert "pre-commit run --all-files" in template


def test_public_bootstrap_package_exposes_npx_installer() -> None:
    repo_root = _repo_root()
    package_json = json.loads((repo_root / "package.json").read_text(encoding="utf-8"))
    packaged_files = set(package_json.get("files", []))

    assert package_json["name"] == "get-physics-done"
    assert package_json["repository"] == {
        "type": "git",
        "url": "git+https://github.com/psi-oss/get-physics-done.git",
    }
    assert package_json.get("engines") == {"node": ">=20"}
    assert package_json.get("bin", {}).get("get-physics-done") == "bin/install.js"
    assert "bin/" in packaged_files
    assert set(_BOOTSTRAP_JSON_ASSETS) <= packaged_files
    assert (repo_root / "bin" / "install.js").is_file()


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
    assert "gpdPythonVersion" in content
    assert '["-m", "venv", "--help"]' in content
    assert "managed environment" in content
    assert 'const GITHUB_MAIN_BRANCH = "main"' in content
    assert "installManagedPackage(managedEnv.python, pythonPackageVersion" in content
    assert "archive/refs/tags/v${version}.tar.gz" in content
    assert "archive/refs/heads/${GITHUB_MAIN_BRANCH}.tar.gz" in content
    assert "git+${repoGitUrl}@v${version}" in content
    assert "git+${repoGitUrl}@${GITHUB_MAIN_BRANCH}" in content
    assert "function repositoryGitUrl(" in content
    assert "function repositorySshGitUrl(" not in content
    assert "requestedVersion" in content
    assert "the PyPI pinned release or tagged GitHub release sources" in content
    assert "the latest unreleased GitHub ${GITHUB_MAIN_BRANCH} source" in content


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


def test_merge_gate_workflow_uses_main_branch_pytest_on_python_floor() -> None:
    repo_root = _repo_root()
    workflow = (repo_root / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
    workflow_data = yaml.safe_load(workflow)
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")

    assert "name: tests" in workflow
    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert "branches: [main]" in workflow
    assert "workflow_dispatch:" in workflow
    assert f"name: pytest ${{{{ matrix.display_name }}}} ({MIN_SUPPORTED_PYTHON_LABEL})" in workflow
    assert "actions/setup-python@v6" in workflow
    assert f'python-version: "{MIN_SUPPORTED_PYTHON_LABEL}"' in workflow
    assert "astral-sh/setup-uv@v7" in workflow
    assert "Check repo graph generated artifacts" in workflow
    assert "python scripts/sync_repo_graph_contract.py --check" in workflow
    assert 'addopts = "-n auto --dist=worksteal"' in pyproject
    assert_ci_workflow_pytest_shard_policy(workflow_data, pyproject_text=pyproject)

    # Staging rebuild trigger lives in a separate workflow (staging-rebuild.yml)
    # to avoid showing as a skipped check on PRs. It gates on tests via workflow_run.
    rebuild_workflow = (repo_root / ".github" / "workflows" / "staging-rebuild.yml").read_text(encoding="utf-8")
    assert 'workflows: ["tests"]' in rebuild_workflow
    assert "conclusion == 'success'" in rebuild_workflow


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
    assert "uv lock" in workflow
    assert "uv run pytest tests/test_release_consistency.py -v" in workflow
    assert "uv build --out-dir dist" in workflow
    assert "rm -rf dist\n          uv build --out-dir dist" in workflow
    assert "npm pack --dry-run --json" in workflow
    assert "gh pr create" in workflow
    assert 'git add CHANGELOG.md CITATION.cff README.md package.json pyproject.toml uv.lock' in workflow
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
    assert "release_sha:" in workflow
    assert "ref: ${{ inputs.release_sha || github.sha }}" in workflow
    assert "git merge-base --is-ancestor HEAD" in workflow
    assert "scripts/release_workflow.py show-version" in workflow
    assert "scripts/release_workflow.py stamp-publish-date" in workflow
    assert "Check existing release tag safety" in workflow
    assert 'TAG_SHA="$(git rev-list -n 1 "v${VERSION}")"' in workflow
    assert "Tag v${VERSION} already points at release commit ${RELEASE_SHA}; continuing publish recovery." in workflow
    assert "Tag v${VERSION} already exists at ${TAG_SHA}, not release commit ${RELEASE_SHA}." in workflow
    assert "environment:" in workflow
    assert "name: PyPI" in workflow
    assert "id-token: write" in workflow
    assert "skip-existing: true" in workflow
    assert "actions/checkout@v6" in workflow
    assert "actions/setup-python@v6" in workflow
    assert "actions/setup-node@v6" in workflow
    assert workflow.count('node-version: "20"') == 1
    assert workflow.count('node-version: "24"') == 1
    assert re.search(r"  publish-npm-and-github-release:\n(?:.*\n)*?          node-version: \"24\"", workflow)
    assert "actions/upload-artifact@v7" in workflow
    assert "actions/download-artifact@v8" in workflow
    assert "pypa/gh-action-pypi-publish@release/v1" in workflow
    assert "name: npm" in workflow
    assert "NODE_AUTH_TOKEN" not in workflow
    assert "NPM_TOKEN" not in workflow
    assert "pull-requests: write" in workflow
    assert "npm publish" in workflow
    assert 'npm view "get-physics-done@${VERSION}" version' in workflow
    assert "status=already-published" in workflow
    assert "status=published" in workflow
    assert "get-physics-done@${VERSION} is already published on npm; skipping npm publish." in workflow
    assert "npm publish failed, but get-physics-done@${VERSION} is now published; continuing." in workflow
    assert "gh release create" in workflow
    assert "git fetch --tags origin" in workflow
    assert "--verify-tag" in workflow
    assert "GitHub release v${VERSION} already exists at the reviewed release commit; continuing publish recovery." in workflow
    assert "Tag v${VERSION} exists at ${TAG_SHA}, not release commit ${RELEASE_SHA}." in workflow
    assert "post-release/v${VERSION}-publish-date" in workflow
    assert "ref: ${{ needs.build-release.outputs.release_sha }}" in workflow
    assert "Run stamped release validation" in workflow
    assert workflow.index("Stamp actual publish date in release checkout") < workflow.index("Run stamped release validation")
    assert workflow.index("Run stamped release validation") < workflow.index("Publish to npm")
    assert "uv run pytest tests/test_release_consistency.py -v" in workflow
    assert "rm -rf dist\n          uv build --out-dir dist" in workflow
    assert 'rm -rf dist\n          npm_config_cache="$(mktemp -d)" npm pack --dry-run --json >/tmp/npm-pack.json' in workflow
    assert (
        'rm -rf dist\n          npm_config_cache="$(mktemp -d)" npm pack --dry-run --json >/tmp/npm-pack-publish.json'
        in workflow
    )
    assert 'npm_config_cache="$(mktemp -d)" npm pack --dry-run --json >/tmp/npm-pack-publish.json' in workflow
    assert "scripts/release_workflow.py release-notes" in workflow
    assert "gh pr create" in workflow
    assert "id: gpd_web_rebuild" in workflow
    assert "GPD_WEB_DISPATCH_TOKEN not configured" in workflow
    assert 'echo "status=skipped" >> "$GITHUB_OUTPUT"' in workflow
    assert 'echo "status=dispatched" >> "$GITHUB_OUTPUT"' in workflow
    assert "NPM_PUBLISH_STATUS: ${{ steps.npm_publish.outputs.status }}" in workflow
    assert 'if [ "${NPM_PUBLISH_STATUS}" = "already-published" ]; then' in workflow
    assert 'echo "- npm: already published; skipped trusted-publishing rerun"' in workflow
    assert 'echo "- npm: published via trusted publishing from environment \\`npm\\`"' in workflow
    assert "GPD_WEB_REBUILD_STATUS: ${{ steps.gpd_web_rebuild.outputs.status }}" in workflow
    assert 'if [ "${GPD_WEB_REBUILD_STATUS}" = "dispatched" ]; then' in workflow
    assert 'echo "- GPD Web production rebuild: dispatched"' in workflow
    assert (
        'echo "- GPD Web production rebuild: skipped; \\`GPD_WEB_DISPATCH_TOKEN\\` is not configured"'
        in workflow
    )
    summary_lines = [line.strip() for line in workflow.splitlines()]
    condition_index = summary_lines.index('if [ "${GPD_WEB_REBUILD_STATUS}" = "dispatched" ]; then')
    dispatched_index = summary_lines.index('echo "- GPD Web production rebuild: dispatched"')
    else_index = next(index for index in range(condition_index + 1, len(summary_lines)) if summary_lines[index] == "else")
    skipped_index = summary_lines.index(
        'echo "- GPD Web production rebuild: skipped; \\`GPD_WEB_DISPATCH_TOKEN\\` is not configured"'
    )
    fi_index = next(index for index in range(else_index + 1, len(summary_lines)) if summary_lines[index] == "fi")
    assert condition_index < dispatched_index < else_index < skipped_index < fi_index


def test_publish_release_followup_recreates_or_fails_when_branch_exists_without_open_pr() -> None:
    repo_root = _repo_root()
    workflow = (repo_root / ".github" / "workflows" / "publish-release.yml").read_text(encoding="utf-8")
    force_with_lease_push = (
        'git push --force-with-lease="refs/heads/${FOLLOWUP_BRANCH}:${EXISTING_BRANCH_SHA}" '
        'origin "HEAD:${FOLLOWUP_BRANCH}"'
    )
    branch_exists_block = workflow[
        workflow.index('if git ls-remote --exit-code --heads origin "$FOLLOWUP_BRANCH"')
        : workflow.index('prepare_followup_branch\n          git push --set-upstream origin "$FOLLOWUP_BRANCH"')
    ]

    assert 'if [ -n "$PR_URL" ]; then' in branch_exists_block
    assert "--jq '.[0].url // \"\"'" in branch_exists_block
    assert 'EXISTING_BRANCH_SHA="$(git ls-remote --heads origin "$FOLLOWUP_BRANCH" | awk' in branch_exists_block
    assert 'echo "::warning::Follow-up branch ${FOLLOWUP_BRANCH} already exists, but no open PR was found' in branch_exists_block
    assert "restamping and updating the branch before recreating the PR" in branch_exists_block
    assert "prepare_followup_branch" in branch_exists_block
    assert force_with_lease_push in branch_exists_block
    assert 'gh pr create --base "$DEFAULT_BRANCH" --head "$FOLLOWUP_BRANCH"' in branch_exists_block
    assert 'if [ -z "$PR_URL" ]; then' in branch_exists_block
    assert 'echo "::error::Follow-up branch ${FOLLOWUP_BRANCH} exists, but no open PR URL could be found' in branch_exists_block
    assert branch_exists_block.index('if [ -n "$PR_URL" ]; then') < branch_exists_block.index(
        "prepare_followup_branch"
    )
    assert branch_exists_block.index("prepare_followup_branch") < branch_exists_block.index(force_with_lease_push)
    assert branch_exists_block.index(force_with_lease_push) < branch_exists_block.index(
        'gh pr create --base "$DEFAULT_BRANCH" --head "$FOLLOWUP_BRANCH"'
    ) < branch_exists_block.index("if [ -z \"$PR_URL\" ]; then")


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
    assert optional == _EXPECTED_OPTIONAL_DEPENDENCIES


def test_optional_publication_imports_stay_explicitly_declared_integrations() -> None:
    repo_root = _repo_root()
    project = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    dependencies: list[str] = project["dependencies"]
    optional = project.get("optional-dependencies", {})
    runtime_requirement_names = _normalized_dependency_names(dependencies)
    optional_requirement_names = _normalized_dependency_names(
        [requirement for requirements in optional.values() for requirement in requirements]
    )

    for relative_path, expected_imports in _OPTIONAL_DECLARED_PUBLICATION_IMPORTS.items():
        direct_imports = _direct_imported_modules(repo_root, relative_path)
        assert direct_imports & expected_imports == expected_imports
        assert not expected_imports & runtime_requirement_names
        assert expected_imports <= optional_requirement_names


def test_registry_command_surface_rewrite_surfaces_live_registry_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    import gpd.command_labels as command_labels

    def _raise_registry_error(*, name_format: str) -> list[str]:
        raise RuntimeError(f"registry parse failed for {name_format}")

    monkeypatch.setattr(
        command_labels,
        "_load_content_registry",
        lambda: SimpleNamespace(list_commands=_raise_registry_error),
    )

    with pytest.raises(RuntimeError, match="registry parse failed for slug"):
        command_labels.rewrite_runtime_command_surfaces("$gpd-help", canonical="command")


def test_model_visible_command_note_surfaces_live_registry_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    import gpd.core.model_visible_text as model_visible_text

    def _raise_registry_error() -> tuple[str, ...]:
        raise RuntimeError("registry agent parse failed")

    monkeypatch.setattr(model_visible_text, "_load_canonical_agent_names", lambda: _raise_registry_error)

    with pytest.raises(RuntimeError, match="registry agent parse failed"):
        model_visible_text.command_visibility_note()


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
        assert json.loads(content) == expected_descriptors[path.stem]

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


def test_gitignore_covers_local_gpd_fix_reports() -> None:
    repo_root = _repo_root()
    content = (repo_root / ".gitignore").read_text(encoding="utf-8")

    assert "GPD-FIX-REPORT-*.md" in content


def test_gitignore_covers_runtime_config_dirs_from_runtime_catalog() -> None:
    repo_root = _repo_root()
    content = (repo_root / ".gitignore").read_text(encoding="utf-8").splitlines()
    ignored_dirs = {line.strip() for line in content if line.strip().endswith("/")}
    expected_dirs = {".agents/", *(f"{descriptor.config_dir_name}/" for descriptor in iter_runtime_descriptors())}

    assert expected_dirs <= ignored_dirs


def test_gitignore_does_not_exclude_gpd_directory() -> None:
    """Assert GPD/ is not gitignored.

    Workflow commit commands (``gpd commit``) include GPD/ files; gitignoring
    them causes ``git add`` failures.  A pre-commit hook strips GPD/ from
    commits to the codebase repo instead.
    """
    repo_root = _repo_root()
    content = (repo_root / ".gitignore").read_text(encoding="utf-8")
    for pattern in ("GPD/", "GPD/*", "GPD/STATE.md", "GPD/state.json", "GPD/state.json.bak", "GPD/state.json.lock"):
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


def test_human_author_check_rejects_lowercase_codex_coauthor_in_range(tmp_path: Path) -> None:
    repo_root = _repo_root()
    hook_script = repo_root / "scripts" / "check-human-authors.sh"

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "human@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Human Author"], cwd=tmp_path, check=True)

    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=tmp_path, check=True, capture_output=True, text=True)

    (tmp_path / "README.md").write_text("seed\nchange\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "change", "-m", "co-authored-by: Codex"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        ["sh", str(hook_script), "--range", "HEAD~1..HEAD"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "non-human co-author lines found" in result.stderr
    assert "change" in result.stderr


def test_npm_pack_dry_run_uses_temp_cache_outside_repo(tmp_path: Path) -> None:
    repo_root = _repo_root()
    if shutil.which("npm") is None:
        pytest.skip("npm is not available")

    repo_cache = repo_root / ".npm-cache"
    existed_before = repo_cache.exists()
    before_paths = (
        sorted(path.relative_to(repo_cache).as_posix() for path in repo_cache.rglob("*"))
        if existed_before
        else []
    )

    pack = _npm_pack_dry_run(repo_root, tmp_path)
    packed_paths = _packaged_file_paths(pack)

    assert pack["name"] == "get-physics-done"
    assert pack["version"] == _python_release_version(repo_root)
    assert "bin/install.js" in packed_paths
    assert "package.json" in packed_paths
    assert set(_BOOTSTRAP_JSON_ASSETS) <= packed_paths
    assert (tmp_path / "npm-cache").is_dir()

    if existed_before:
        after_paths = sorted(path.relative_to(repo_cache).as_posix() for path in repo_cache.rglob("*"))
        assert after_paths == before_paths
    else:
        assert not repo_cache.exists()


def test_python_sdist_excludes_local_generated_artifacts(tmp_path: Path) -> None:
    repo_root = _repo_root()
    uv = shutil.which("uv")
    assert uv is not None, "uv is required for sdist validation"
    build_root = tmp_path / "checkout"
    output_dir = tmp_path / "sdist-output"
    output_dir.mkdir()
    _copy_checkout_for_release_test(repo_root, build_root)

    uv_cache = tmp_path / "uv-cache"
    env = os.environ.copy()
    env.update(
        {
            "UV_CACHE_DIR": str(uv_cache),
            "UV_NO_CONFIG": "1",
            "UV_PYTHON_DOWNLOADS": "never",
        }
    )

    seeded_artifacts = (
        (build_root / "__pycache__" / "gpd-sdist-hygiene-leak.pyc", b"pyc"),
        (build_root / "src" / "gpd" / "__pycache__" / "gpd-sdist-hygiene-leak.pyc", b"pyc"),
        (build_root / "tests" / "gpd-sdist-hygiene-leak.pyo", b"pyo"),
        (build_root / ".npm-cache" / "gpd-sdist-hygiene-leak.txt", b"cache"),
        (build_root / ".uv-cache" / "gpd-sdist-hygiene-leak.txt", b"uv-cache"),
        (build_root / "build" / "gpd-sdist-hygiene-leak.txt", b"build"),
        (build_root / "dist" / "gpd-sdist-hygiene-leak.tar.gz", b"dist"),
        (build_root / "tmp" / "gpd-sdist-hygiene-leak.txt", b"tmp"),
        (build_root / "GPD-FIX-REPORT" / "gpd-sdist-hygiene-leak.txt", b"gpd"),
        (build_root / "get_physics_done.egg-info" / "PKG-INFO", b"Name: leak\n"),
    )
    for path, payload in seeded_artifacts:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    result = subprocess.run(
        [uv, "build", "--sdist", "--out-dir", str(output_dir)],
        cwd=build_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0 and _uv_build_blocked_by_environment(result.stderr):
        pytest.skip(f"uv build is blocked by the local uv/runtime environment: {result.stderr.strip()}")
    assert result.returncode == 0, result.stderr or result.stdout

    archives = sorted(output_dir.glob("get_physics_done-*.tar.gz"))
    assert len(archives) == 1
    root = f"get_physics_done-{_python_release_version(build_root)}/"
    with tarfile.open(archives[0], "r:gz") as archive:
        names = set(archive.getnames())

    assert f"{root}src/gpd/cli.py" in names
    assert f"{root}bin/install.js" in names
    assert f"{root}README.md" in names
    assert f"{root}.github/workflows/test.yml" in names
    assert f"{root}.gitignore" in names
    assert f"{root}.pre-commit-config.yaml" in names

    forbidden_fragments = (
        ".DS_Store",
        "__pycache__/",
        ".mypy_cache/",
        ".npm-cache/",
        ".pytest_cache/",
        ".ruff_cache/",
        ".uv-cache/",
        ".venv/",
        ".egg-info/",
        ".pyc",
        ".pyo",
        "/build/",
        "/GPD-FIX-REPORT",
        "/dist/",
        "/tmp/",
    )
    assert not [
        name
        for name in sorted(names)
        if any(fragment in name for fragment in forbidden_fragments)
    ]


def test_python_wheel_contains_public_metadata_console_scripts_and_package_data(tmp_path: Path) -> None:
    repo_root = _repo_root()
    uv = shutil.which("uv")
    assert uv is not None, "uv is required for wheel validation"
    build_root = tmp_path / "checkout"
    output_dir = tmp_path / "wheel-output"
    output_dir.mkdir()
    _copy_checkout_for_release_test(repo_root, build_root)

    uv_cache = tmp_path / "uv-cache"
    env = os.environ.copy()
    env.update(
        {
            "UV_CACHE_DIR": str(uv_cache),
            "UV_NO_CONFIG": "1",
            "UV_PYTHON_DOWNLOADS": "never",
        }
    )

    result = subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(output_dir)],
        cwd=build_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0 and _uv_build_blocked_by_environment(result.stderr):
        pytest.skip(f"uv build is blocked by the local uv/runtime environment: {result.stderr.strip()}")
    assert result.returncode == 0, result.stderr or result.stdout

    wheels = sorted(output_dir.glob("get_physics_done-*.whl"))
    assert len(wheels) == 1
    version = _python_release_version(build_root)
    dist_info = f"get_physics_done-{version}.dist-info"
    pyproject = tomllib.loads((build_root / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]

    with zipfile.ZipFile(wheels[0]) as wheel:
        names = set(wheel.namelist())
        metadata = wheel.read(f"{dist_info}/METADATA").decode("utf-8")
        entry_points = wheel.read(f"{dist_info}/entry_points.txt").decode("utf-8")

    assert f"Name: {project['name']}" in metadata
    assert f"Version: {version}" in metadata
    assert f"Summary: {project['description']}" in metadata
    assert f"Requires-Python: {project['requires-python']}" in metadata
    assert f"Author: {project['authors'][0]['name']}" in metadata
    assert f"Maintainer: {project['maintainers'][0]['name']}" in metadata
    for label, url in project["urls"].items():
        assert f"Project-URL: {label}, {url}" in metadata
    assert _wheel_dependency_names(metadata) == _expected_wheel_dependency_names()

    expected_entry_points = {f"{name} = {target}" for name, target in project["scripts"].items()}
    actual_entry_points = {line for line in entry_points.splitlines() if " = " in line}
    assert actual_entry_points == expected_entry_points

    expected_package_data = _source_wheel_package_data_paths(build_root / "src" / "gpd")
    missing_package_data = sorted(expected_package_data - names)
    assert not missing_package_data, "wheel is missing required package data:\n" + "\n".join(
        f"- {path}" for path in missing_package_data
    )
    assert {
        "gpd/commands/help.md",
        "gpd/agents/gpd-executor.md",
        "gpd/specs/workflows/new-project.md",
        "gpd/specs/workflows/new-project-stage-manifest.json",
        "gpd/core/public_surface_contract.json",
        "gpd/core/public_surface_contract_schema.json",
        "gpd/adapters/runtime_catalog.json",
        "gpd/specs/templates/paper/referee-report.tex",
        "gpd/specs/templates/slides/main.tex",
        "gpd/mcp/paper/templates/jhep/jhep_template.tex",
    } <= names

    forbidden_fragments = (
        "__pycache__/",
        ".pyc",
        ".pyo",
        "/build/",
        "/dist/",
        "/GPD-FIX-REPORT",
        "/tmp/",
    )
    assert not [
        name
        for name in sorted(names)
        if any(fragment in name for fragment in forbidden_fragments)
    ]



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
    assert citation == re.sub(
        r"^version:\s*[^\n]+$",
        f"version: {next_version}",
        original_citation,
        count=1,
        flags=re.M,
    )

    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert f"version = {{{next_version}}}" in readme
    assert f"(Version {next_version})" in readme
    assert "year = {2026}" in readme
    assert readme == update_readme_version_text(original_readme, next_version)

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

    citation = (tmp_path / "CITATION.cff").read_text(encoding="utf-8")
    match = re.search(r"^date-released: '(\d{4}-\d{2}-\d{2})'$", citation, re.M)
    assert match is not None

    metadata = stamp_publish_date(tmp_path, release_date=match.group(1))

    assert metadata.changed_files == ()


def test_stamp_publish_date_rejects_full_datetime_release_inputs(tmp_path: Path) -> None:
    repo_root = _repo_root()
    _copy_release_surfaces(repo_root, tmp_path)

    with pytest.raises(ReleaseError, match="YYYY-MM-DD"):
        stamp_publish_date(tmp_path, release_date="2026-03-15T12:34:56Z")
