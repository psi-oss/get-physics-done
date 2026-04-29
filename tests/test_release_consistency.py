"""Guardrails for public release consistency."""

from __future__ import annotations

import ast
import json
import os
import posixpath
import re
import shutil
import subprocess
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest
import yaml

from gpd._python_compat import MIN_SUPPORTED_PYTHON_LABEL, PREFERRED_PYTHON_VERSIONS
from gpd.adapters.runtime_catalog import get_shared_install_metadata, iter_runtime_descriptors
from scripts import release_workflow as release_workflow_module
from scripts.release_workflow import (
    ReleaseError,
    bump_version,
    extract_release_notes,
    prepare_release,
    stamp_publish_date,
    update_readme_version_text,
)
from tests.ci_sharding import assert_ci_workflow_pytest_shard_policy
from tests.helpers.git import (
    git_add,
    git_commit,
    git_identity_env,
    init_test_git_repo,
    run_git,
    seed_test_git_repo,
)
from tests.helpers.github_actions import load_repo_github_actions_workflow, workflow_step_by_name, workflow_steps_using
from tests.helpers.release import (
    EXPECTED_SETUP_UV_VERSION,
    assert_run_step_uses_isolated_uv_build_env,
    assert_setup_uv_step_pins_expected_version,
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
_PUBLIC_BOOTSTRAP_PREREQUISITE = "Install GPD before enabling built-in MCP servers."
_ARXIV_EXTRA_PREREQUISITE = (
    "Install GPD with the `arxiv` Python extra in the same environment before enabling gpd-arxiv."
)
_EXPECTED_OPTIONAL_DEPENDENCIES = {
    "paper": ["cairosvg>=2.7.0", "pypdf>=5.0"],
    "arxiv": ["arxiv-mcp-server>=0.4.11", "arxiv>=2.4.1", "cairosvg>=2.7.0", "pypdf>=5.0"],
}
_OPTIONAL_IMPORT_MODULE_TO_DEPENDENCY = {
    "arxiv": "arxiv",
    "cairosvg": "cairosvg",
    "pypdf": "pypdf",
}
_EXPECTED_OPTIONAL_IMPORT_LOCATIONS = {
    "arxiv": {"src/gpd/mcp/paper/bibliography.py"},
    "cairosvg": {"src/gpd/mcp/paper/figures.py"},
    "pypdf": {"src/gpd/core/artifact_text.py", "src/gpd/mcp/paper/compiler.py"},
}
_EXPECTED_OPTIONAL_DEPENDENCY_EXTRAS = {
    "arxiv": {"arxiv"},
    "arxiv-mcp-server": {"arxiv"},
    "cairosvg": {"arxiv", "paper"},
    "pypdf": {"arxiv", "paper"},
}
_EXPECTED_BUILD_BACKEND_REQUIREMENT = "hatchling==1.29.0"


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


def _uv_lock_editable_package(repo_root: Path) -> dict[str, object]:
    lock = tomllib.loads((repo_root / "uv.lock").read_text(encoding="utf-8"))
    packages = lock.get("package", [])
    assert isinstance(packages, list)
    for package in packages:
        if not isinstance(package, dict):
            continue
        if package.get("name") == "get-physics-done" and package.get("source") == {"editable": "."}:
            return package
    raise AssertionError("uv.lock is missing the editable get-physics-done package entry")


def _uv_lock_project_version(repo_root: Path) -> str:
    return str(_uv_lock_editable_package(repo_root)["version"])


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


def _readme_relative_file_links(readme: str) -> set[str]:
    links: set[str] = set()
    for match in re.finditer(r"(?:\[[^\]\n]+\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)|href=\"([^\"]+)\")", readme):
        target = (match.group(1) or match.group(2) or "").strip()
        if not target or target.startswith(("#", "http://", "https://", "mailto:", "tel:")):
            continue
        target = target.split("#", 1)[0].split("?", 1)[0]
        if not target:
            continue
        normalized = posixpath.normpath(target)
        if normalized != ".":
            links.add(normalized)
    return links


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

    return ("failed to open file" in stderr and "/.cache/uv/sdists" in stderr) or (
        "system-configuration" in stderr
        and "Attempted to create a NULL object" in stderr
        and "Tokio executor failed" in stderr
    )


class _FakePypiResponse:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> _FakePypiResponse:
        return self

    def __exit__(self, *_: object) -> None:
        return None


def _mock_pypi_probe(
    monkeypatch: pytest.MonkeyPatch,
    result: _FakePypiResponse | BaseException,
) -> list[tuple[str, float]]:
    calls: list[tuple[str, float]] = []

    def _fake_urlopen(url: str, *, timeout: float) -> _FakePypiResponse:
        calls.append((url, timeout))
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(release_workflow_module.urllib.request, "urlopen", _fake_urlopen)
    return calls


def _copy_checkout_for_release_test(repo_root: Path, destination: Path) -> None:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "-z"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    destination.mkdir(parents=True, exist_ok=True)
    for path_text in result.stdout.split("\0"):
        if not path_text:
            continue
        relative_path = Path(path_text)
        assert not relative_path.is_absolute()
        assert ".." not in relative_path.parts
        source = repo_root / relative_path
        assert source.exists(), f"tracked source path is missing from release copy fixture: {relative_path}"
        target = destination / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target, follow_symlinks=False)


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


def _optional_import_locations(repo_root: Path, module_names: set[str]) -> dict[str, set[str]]:
    locations: dict[str, set[str]] = {module_name: set() for module_name in module_names}
    for path in sorted((repo_root / "src" / "gpd").rglob("*.py")):
        relative_path = path.relative_to(repo_root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
        for node in ast.walk(tree):
            imported_modules: set[str] = set()
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module.split(".", 1)[0])
            for module_name in imported_modules & module_names:
                locations[module_name].add(relative_path)
    return {module_name: paths for module_name, paths in sorted(locations.items()) if paths}


def _string_constant_assignments(repo_root: Path, relative_path: str) -> dict[str, str]:
    tree = ast.parse((repo_root / relative_path).read_text(encoding="utf-8"), filename=relative_path)
    assignments: dict[str, str] = {}
    for node in ast.walk(tree):
        if (
            not isinstance(node, ast.Assign)
            or not isinstance(node.value, ast.Constant)
            or not isinstance(node.value.value, str)
        ):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                assignments[target.id] = node.value.value
    return assignments


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
        requirement for requirements in _EXPECTED_OPTIONAL_DEPENDENCIES.values() for requirement in requirements
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


def _dependency_label(requirement: str) -> str:
    match = re.match(r"([A-Za-z0-9_.-]+)(?:\[.*?\])?", requirement.strip())
    assert match is not None, requirement
    return match.group(1)


def _normalized_dependency_names(requirements: list[str]) -> set[str]:
    return {_normalized_requirement_name(requirement) for requirement in requirements}


def _optional_dependency_extras(optional_dependencies: dict[str, list[str]]) -> dict[str, set[str]]:
    extras_by_dependency: dict[str, set[str]] = {}
    for extra_name, requirements in optional_dependencies.items():
        for requirement in requirements:
            dependency_name = _normalized_requirement_name(requirement)
            extras_by_dependency.setdefault(dependency_name, set()).add(extra_name)
    return extras_by_dependency


def _wheel_dependency_names(metadata: str) -> set[str]:
    requirements = [
        line.split(":", 1)[1].strip() for line in metadata.splitlines() if line.startswith("Requires-Dist:")
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


def test_python_build_backend_is_pinned_for_reproducible_release_builds() -> None:
    repo_root = _repo_root()
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    build_system = pyproject["build-system"]

    assert build_system["build-backend"] == "hatchling.build"
    assert build_system["requires"] == [_EXPECTED_BUILD_BACKEND_REQUIREMENT]


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
    assert "uv run pytest -n 0 -q <targets>" in template
    assert "GitHub Actions PR checks" in template
    assert "uv run ruff check ." in template
    assert "pre-commit run --all-files" in template


def test_targeted_release_and_pr_pytest_commands_disable_xdist() -> None:
    repo_root = _repo_root()
    command_sources = (
        ".github/pull_request_template.md",
        ".github/workflows/release.yml",
        ".github/workflows/publish-release.yml",
    )

    offenders: list[str] = []
    for relpath in command_sources:
        text = (repo_root / relpath).read_text(encoding="utf-8")
        for command in re.findall(r"uv run pytest[^\n`]*", text):
            if "tests/" not in command and "<targets>" not in command:
                continue
            parts = command.split()
            if "-n" not in parts or parts[parts.index("-n") + 1 : parts.index("-n") + 2] != ["0"]:
                offenders.append(f"{relpath}: {command.strip()}")

    assert offenders == []


def test_public_bootstrap_package_exposes_npx_installer() -> None:
    repo_root = _repo_root()
    package_json = json.loads((repo_root / "package.json").read_text(encoding="utf-8"))
    packaged_files = package_json.get("files", [])

    assert package_json["name"] == "get-physics-done"
    assert package_json["repository"] == {
        "type": "git",
        "url": "git+https://github.com/psi-oss/get-physics-done.git",
    }
    assert package_json.get("engines") == {"node": ">=20"}
    assert package_json.get("bin", {}).get("get-physics-done") == "bin/install.js"
    assert set(packaged_files) == {"bin/install.js", *_BOOTSTRAP_JSON_ASSETS}
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
    assert "mkdir -p GPD/exports" not in workflow
    assert "Write files to `exports/`." in command
    assert "Files written to exports/" in command
    assert "Write files to `GPD/exports" not in command


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
    workflow_data = load_repo_github_actions_workflow(repo_root, "test.yml")
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")

    assert "name: tests" in workflow
    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert "branches: [main]" in workflow
    assert "workflow_dispatch:" in workflow
    assert f"name: pytest ${{{{ matrix.display_name }}}} ({MIN_SUPPORTED_PYTHON_LABEL})" in workflow
    assert "actions/setup-python@v6" in workflow
    assert f'python-version: "{MIN_SUPPORTED_PYTHON_LABEL}"' in workflow
    assert "name: python compatibility (${{ matrix.python-version }})" in workflow
    assert 'python-version: ["3.12", "3.13"]' in workflow
    assert "uv run gpd --version" in workflow
    assert "uv build --wheel --out-dir dist/compat-${{ matrix.python-version }}" in workflow
    assert "astral-sh/setup-uv@v7" in workflow
    assert f'version: "{EXPECTED_SETUP_UV_VERSION}"' in workflow
    assert "Check repo graph generated artifacts" in workflow
    assert "uv run python scripts/sync_repo_graph_contract.py --check" in workflow
    assert 'addopts = "-n auto --dist=worksteal"' in pyproject
    assert_ci_workflow_pytest_shard_policy(workflow_data, pyproject_text=pyproject)

    # Staging rebuild trigger lives in a separate workflow (staging-rebuild.yml)
    # to avoid showing as a skipped check on PRs. It gates on tests via workflow_run.
    rebuild_workflow = (repo_root / ".github" / "workflows" / "staging-rebuild.yml").read_text(encoding="utf-8")
    assert 'workflows: ["tests"]' in rebuild_workflow
    assert "conclusion == 'success'" in rebuild_workflow
    assert "curl -sf --retry 3 --retry-delay 5 --connect-timeout 10 --max-time 30 -X POST" in rebuild_workflow


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
    assert f'version: "{EXPECTED_SETUP_UV_VERSION}"' in workflow
    assert "uv sync --dev --frozen" in workflow
    assert "scripts/release_workflow.py prepare" in workflow
    assert "uv lock" in workflow
    assert "uv run pytest -n 0 tests/test_release_consistency.py -v" in workflow
    assert "uv build --out-dir dist" in workflow
    assert "npm pack --dry-run --json" in workflow
    assert "gh pr create" in workflow
    assert "--jq '.[0].url // \"\"'" in workflow
    assert "--jq '.[0].url')" not in workflow
    assert "git add CHANGELOG.md CITATION.cff README.md package.json pyproject.toml uv.lock" in workflow
    assert "Publish release" in workflow
    assert "pypa/gh-action-pypi-publish@release/v1" not in workflow
    assert "npm publish" not in workflow
    assert "gh release create" not in workflow


def test_pypi_preflight_helper_records_already_published_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    github_output = tmp_path / "github-output.txt"
    calls = _mock_pypi_probe(monkeypatch, _FakePypiResponse(200))

    status = release_workflow_module.record_pypi_preflight_status(
        "get-physics-done",
        "1.2.3",
        github_output=github_output,
    )

    assert status == "already-published"
    assert github_output.read_text(encoding="utf-8") == "status=already-published\n"
    assert calls == [("https://pypi.org/pypi/get-physics-done/1.2.3/json", 20.0)]
    assert "get-physics-done 1.2.3 is already published on PyPI; skipping PyPI publish." in capsys.readouterr().out


def test_pypi_preflight_helper_attempts_publish_when_probe_is_inconclusive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    github_output = tmp_path / "github-output.txt"
    _mock_pypi_probe(monkeypatch, OSError("temporary network failure"))

    status = release_workflow_module.record_pypi_preflight_status(
        "get-physics-done",
        "1.2.3",
        github_output=github_output,
    )

    captured = capsys.readouterr()
    assert status == "not-published"
    assert github_output.read_text(encoding="utf-8") == "status=not-published\n"
    assert "Could not determine whether get-physics-done 1.2.3 is already on PyPI" in captured.out
    assert "PyPI version check failed: temporary network failure" in captured.err


def test_pypi_publish_status_helper_reuses_preflight_already_published_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    github_output = tmp_path / "github-output.txt"

    def _unexpected_urlopen(*_: object, **__: object) -> None:
        raise AssertionError("preflight already-published status should not probe PyPI again")

    monkeypatch.setattr(release_workflow_module.urllib.request, "urlopen", _unexpected_urlopen)

    status = release_workflow_module.record_pypi_publish_status(
        "get-physics-done",
        "1.2.3",
        pre_publish_status="already-published",
        publish_outcome="skipped",
        github_output=github_output,
    )

    assert status == "already-published"
    assert github_output.read_text(encoding="utf-8") == "status=already-published\n"


def test_pypi_publish_status_helper_records_success_after_preflight_not_published(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    github_output = tmp_path / "github-output.txt"

    def _unexpected_urlopen(*_: object, **__: object) -> None:
        raise AssertionError("successful publish should not probe PyPI again")

    monkeypatch.setattr(release_workflow_module.urllib.request, "urlopen", _unexpected_urlopen)

    status = release_workflow_module.record_pypi_publish_status(
        "get-physics-done",
        "1.2.3",
        pre_publish_status="not-published",
        publish_outcome="success",
        github_output=github_output,
    )

    assert status == "published"
    assert github_output.read_text(encoding="utf-8") == "status=published\n"


def test_pypi_publish_status_helper_recovers_when_failed_publish_is_visible_on_pypi(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    github_output = tmp_path / "github-output.txt"
    _mock_pypi_probe(monkeypatch, _FakePypiResponse(200))

    status = release_workflow_module.record_pypi_publish_status(
        "get-physics-done",
        "1.2.3",
        pre_publish_status="not-published",
        publish_outcome="failure",
        github_output=github_output,
    )

    assert status == "recovered"
    assert github_output.read_text(encoding="utf-8") == "status=recovered\n"
    assert "PyPI publish failed, but get-physics-done 1.2.3 is now published; continuing." in capsys.readouterr().out


def test_pypi_publish_status_helper_fails_when_publish_and_recovery_probe_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = release_workflow_module.urllib.error.HTTPError(
        "https://pypi.org/pypi/get-physics-done/1.2.3/json",
        404,
        "Not Found",
        hdrs=None,
        fp=None,
    )
    _mock_pypi_probe(monkeypatch, error)

    with pytest.raises(
        ReleaseError,
        match="PyPI publish did not complete and get-physics-done 1.2.3 is not published.",
    ):
        release_workflow_module.record_pypi_publish_status(
            "get-physics-done",
            "1.2.3",
            pre_publish_status="not-published",
            publish_outcome="failure",
        )


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
    workflow_data = load_repo_github_actions_workflow(repo_root, "publish-release.yml")
    setup_uv_steps = workflow_steps_using(workflow_data, "astral-sh/setup-uv@v7")
    assert setup_uv_steps
    for _, step in setup_uv_steps:
        assert_setup_uv_step_pins_expected_version(step, context="publish-release.yml")
    assert "Check existing release tag safety" in workflow
    assert 'TAG_SHA="$(git rev-list -n 1 "v${VERSION}")"' in workflow
    assert "Tag v${VERSION} already points at release commit ${RELEASE_SHA}; continuing publish recovery." in workflow
    assert "Tag v${VERSION} already exists at ${TAG_SHA}, not release commit ${RELEASE_SHA}." in workflow
    assert "environment:" in workflow
    assert "name: PyPI" in workflow
    assert re.search(
        r"  publish-pypi:\n(?:.*\n)*?    permissions:\n      contents: read\n      id-token: write",
        workflow,
    )
    assert "id-token: write" in workflow
    assert "status: ${{ steps.pypi_status.outputs.status }}" in workflow
    assert "Check out release helper" in workflow
    assert "id: pypi_preflight" in workflow
    assert "id: pypi_publish" in workflow
    assert "continue-on-error: true" in workflow
    assert "id: pypi_status" in workflow
    assert workflow.count("python3 scripts/release_workflow.py pypi-preflight") == 1
    assert workflow.count("python3 scripts/release_workflow.py pypi-publish-status") == 1
    assert '--github-output "$GITHUB_OUTPUT"' in workflow
    assert '--pre-publish-status "$PRE_PUBLISH_STATUS"' in workflow
    assert '--publish-outcome "$PYPI_PUBLISH_OUTCOME"' in workflow
    assert "PYPI_CHECK_STATUS=0" not in workflow
    assert "pypi_version_is_published()" not in workflow
    assert "urllib.request" not in workflow
    assert "https://pypi.org/pypi/get-physics-done" not in workflow
    assert "PYPI_PUBLISH_OUTCOME: ${{ steps.pypi_publish.outcome }}" in workflow
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
    assert (
        "GitHub release v${VERSION} already exists at the reviewed release commit; continuing publish recovery."
        in workflow
    )
    assert "Tag v${VERSION} exists at ${TAG_SHA}, not release commit ${RELEASE_SHA}." in workflow
    assert "post-release/v${VERSION}-publish-date" in workflow
    assert "remote_followup_branch_sha()" in workflow
    assert "refresh_followup_branch()" in workflow
    assert "verify_followup_branch_matches_fresh_stamp()" in workflow
    assert "refreshing stamped metadata before returning its URL" in workflow
    assert 'git push --force-with-lease="refs/heads/${FOLLOWUP_BRANCH}:${EXISTING_BRANCH_SHA}"' in workflow
    assert (
        'git fetch --no-tags origin "refs/heads/${FOLLOWUP_BRANCH}:refs/remotes/origin/${FOLLOWUP_BRANCH}"' in workflow
    )
    assert "does not match freshly stamped publish-date metadata" in workflow
    assert workflow.index("refreshing stamped metadata before returning its URL") < workflow.index(
        'echo "pr_url=${PR_URL}" >> "$GITHUB_OUTPUT"'
    )
    assert workflow.index("refresh_followup_branch") < workflow.index(
        'gh pr create --base "$DEFAULT_BRANCH" --head "$FOLLOWUP_BRANCH"'
    )
    assert "ref: ${{ needs.build-release.outputs.release_sha }}" in workflow
    assert "Run stamped release validation" in workflow
    assert workflow.index("Stamp actual publish date in release checkout") < workflow.index(
        "Run stamped release validation"
    )
    assert workflow.index("Run stamped release validation") < workflow.index("Publish to npm")
    assert "uv run pytest -n 0 tests/test_release_consistency.py -v" in workflow
    assert (
        'rm -rf dist\n          npm_config_cache="$(mktemp -d)" npm pack --dry-run --json >/tmp/npm-pack-publish.json'
        in workflow
    )
    assert 'npm_config_cache="$(mktemp -d)" npm pack --dry-run --json >/tmp/npm-pack-publish.json' in workflow
    assert "scripts/release_workflow.py release-notes" in workflow
    assert "gh pr create" in workflow
    assert "id: gpd_web_rebuild" in workflow
    assert "curl -sf --retry 3 --retry-delay 5 --connect-timeout 10 --max-time 30 -X POST" in workflow
    assert "GPD_WEB_DISPATCH_TOKEN not configured" in workflow
    assert 'echo "status=skipped" >> "$GITHUB_OUTPUT"' in workflow
    assert 'echo "status=dispatched" >> "$GITHUB_OUTPUT"' in workflow
    assert "PYPI_PUBLISH_STATUS: ${{ needs.publish-pypi.outputs.status }}" in workflow
    assert 'if [ "${PYPI_PUBLISH_STATUS}" = "already-published" ]; then' in workflow
    assert 'echo "- PyPI: already published; skipped trusted-publishing rerun"' in workflow
    assert 'elif [ "${PYPI_PUBLISH_STATUS}" = "recovered" ]; then' in workflow
    assert 'echo "- PyPI: publish recovery completed; version is present on PyPI"' in workflow
    assert 'echo "- PyPI: published via trusted publishing from environment \\`PyPI\\`"' in workflow
    assert "NPM_PUBLISH_STATUS: ${{ steps.npm_publish.outputs.status }}" in workflow
    assert 'if [ "${NPM_PUBLISH_STATUS}" = "already-published" ]; then' in workflow
    assert 'echo "- npm: already published; skipped trusted-publishing rerun"' in workflow
    assert 'echo "- npm: published via trusted publishing from environment \\`npm\\`"' in workflow
    assert "GPD_WEB_REBUILD_STATUS: ${{ steps.gpd_web_rebuild.outputs.status }}" in workflow
    assert 'if [ "${GPD_WEB_REBUILD_STATUS}" = "dispatched" ]; then' in workflow
    assert 'echo "- GPD Web production rebuild: dispatched"' in workflow
    assert 'echo "- GPD Web production rebuild: skipped; \\`GPD_WEB_DISPATCH_TOKEN\\` is not configured"' in workflow
    summary_lines = [line.strip() for line in workflow.splitlines()]
    condition_index = summary_lines.index('if [ "${GPD_WEB_REBUILD_STATUS}" = "dispatched" ]; then')
    dispatched_index = summary_lines.index('echo "- GPD Web production rebuild: dispatched"')
    else_index = next(
        index for index in range(condition_index + 1, len(summary_lines)) if summary_lines[index] == "else"
    )
    skipped_index = summary_lines.index(
        'echo "- GPD Web production rebuild: skipped; \\`GPD_WEB_DISPATCH_TOKEN\\` is not configured"'
    )
    fi_index = next(index for index in range(else_index + 1, len(summary_lines)) if summary_lines[index] == "fi")
    assert condition_index < dispatched_index < else_index < skipped_index < fi_index


def test_release_workflow_uv_build_steps_use_isolated_uv_environment() -> None:
    repo_root = _repo_root()

    release_workflow = load_repo_github_actions_workflow(repo_root, "release.yml")
    publish_workflow = load_repo_github_actions_workflow(repo_root, "publish-release.yml")
    assert_run_step_uses_isolated_uv_build_env(
        workflow_step_by_name(release_workflow, "prepare-release", "Run release validation suite"),
        context="release.yml prepare-release Run release validation suite",
    )
    assert_run_step_uses_isolated_uv_build_env(
        workflow_step_by_name(publish_workflow, "build-release", "Build Python distributions"),
        context="publish-release.yml build-release Build Python distributions",
    )


def test_release_workflows_pin_setup_uv_tool_version_structurally() -> None:
    repo_root = _repo_root()
    workflow_names = ("release.yml", "publish-release.yml")
    setup_uv_step_count = 0

    for workflow_name in workflow_names:
        workflow = load_repo_github_actions_workflow(repo_root, workflow_name)
        setup_uv_steps = workflow_steps_using(workflow, "astral-sh/setup-uv@v7")
        setup_uv_step_count += len(setup_uv_steps)
        for job_id, step in setup_uv_steps:
            assert_setup_uv_step_pins_expected_version(step, context=f"{workflow_name}:{job_id}")

    assert setup_uv_step_count == 3


def test_publish_release_followup_recreates_or_fails_when_branch_exists_without_open_pr() -> None:
    repo_root = _repo_root()
    workflow = (repo_root / ".github" / "workflows" / "publish-release.yml").read_text(encoding="utf-8")
    force_with_lease_push = (
        'git push --force-with-lease="refs/heads/${FOLLOWUP_BRANCH}:${EXISTING_BRANCH_SHA}" '
        'origin "HEAD:${FOLLOWUP_BRANCH}"'
    )
    branch_exists_block = workflow[
        workflow.index('if git ls-remote --exit-code --heads origin "$FOLLOWUP_BRANCH"') : workflow.index(
            'prepare_followup_branch\n          git push --set-upstream origin "$FOLLOWUP_BRANCH"'
        )
    ]

    assert "remote_followup_branch_sha()" in workflow
    assert "refresh_followup_branch()" in workflow
    assert force_with_lease_push in workflow
    assert 'if [ -n "$PR_URL" ]; then' in branch_exists_block
    assert "--jq '.[0].url // \"\"'" in branch_exists_block
    assert "refreshing stamped metadata before returning its URL" in branch_exists_block
    assert "refresh_followup_branch" in branch_exists_block
    assert (
        'echo "::warning::Follow-up branch ${FOLLOWUP_BRANCH} already exists, but no open PR was found'
        in branch_exists_block
    )
    assert "restamping and updating the branch before recreating the PR" in branch_exists_block
    assert 'gh pr create --base "$DEFAULT_BRANCH" --head "$FOLLOWUP_BRANCH"' in branch_exists_block
    assert 'if [ -z "$PR_URL" ]; then' in branch_exists_block
    assert (
        'echo "::error::Follow-up branch ${FOLLOWUP_BRANCH} exists, but no open PR URL could be found'
        in branch_exists_block
    )
    open_pr_refresh_index = branch_exists_block.index("refreshing stamped metadata before returning its URL")
    no_pr_refresh_index = branch_exists_block.rindex("refresh_followup_branch")
    assert branch_exists_block.index('if [ -n "$PR_URL" ]; then') < open_pr_refresh_index
    assert open_pr_refresh_index < branch_exists_block.index('echo "pr_url=${PR_URL}" >> "$GITHUB_OUTPUT"')
    assert (
        branch_exists_block.index("restamping and updating the branch before recreating the PR") < no_pr_refresh_index
    )
    assert (
        no_pr_refresh_index
        < branch_exists_block.index('gh pr create --base "$DEFAULT_BRANCH" --head "$FOLLOWUP_BRANCH"')
        < branch_exists_block.index('if [ -z "$PR_URL" ]; then')
    )


def test_claude_sdk_is_not_shipped_in_public_install() -> None:
    repo_root = _repo_root()
    project = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    dependencies: list[str] = project["dependencies"]
    optional = project.get("optional-dependencies", {})

    assert not any(item.startswith("claude-agent-sdk") for item in dependencies)
    assert "claude-subagents" not in optional
    assert not any(item.startswith("claude-agent-sdk") for items in optional.values() for item in items)
    assert "scientific" not in optional


def test_public_runtime_dependency_surface_stays_curated() -> None:
    repo_root = _repo_root()
    project = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    dependencies: list[str] = project["dependencies"]
    optional = project.get("optional-dependencies", {})

    assert _normalized_dependency_names(dependencies) == _expected_runtime_dependency_names()
    assert "mcp>=1.27.0" in dependencies
    assert not any(item.startswith("mcp[") for item in dependencies)
    assert optional == _EXPECTED_OPTIONAL_DEPENDENCIES


def test_uv_lock_tracks_runtime_dependency_extras() -> None:
    repo_root = _repo_root()
    lock_package = _uv_lock_editable_package(repo_root)
    dependencies = lock_package.get("dependencies")
    metadata = lock_package.get("metadata")

    assert isinstance(dependencies, list)
    assert isinstance(metadata, dict)
    requires_dist = metadata.get("requires-dist")
    assert isinstance(requires_dist, list)

    assert [item for item in dependencies if isinstance(item, dict) and item.get("name") == "mcp"] == [{"name": "mcp"}]
    assert [item for item in requires_dist if isinstance(item, dict) and item.get("name") == "mcp"] == [
        {"name": "mcp", "specifier": ">=1.27.0"}
    ]


def test_dependency_graph_docs_track_pyproject_dependency_labels() -> None:
    repo_root = _repo_root()
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    readme = (repo_root / "tests" / "README.md").read_text(encoding="utf-8")
    match = re.search(r"- `pyproject\.toml -> external Python packages \{([^}]+)\}`", readme)
    assert match is not None

    graph_labels = {item.strip() for item in match.group(1).split(",")}
    expected_labels = {_dependency_label(requirement) for requirement in project["dependencies"]}
    expected_labels.update(
        _dependency_label(requirement)
        for requirements in project.get("optional-dependencies", {}).values()
        for requirement in requirements
    )
    expected_labels.update(_dependency_label(requirement) for requirement in pyproject["dependency-groups"]["dev"])
    expected_labels.update(_dependency_label(requirement) for requirement in pyproject["build-system"]["requires"])

    assert graph_labels == expected_labels
    assert "mcp" in graph_labels
    assert "mcp[cli]" not in graph_labels


def test_public_python_classifiers_cover_supported_compatibility_minors() -> None:
    repo_root = _repo_root()
    project = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    classifiers = set(project["classifiers"])
    expected_classifiers = {
        f"Programming Language :: Python :: {major}.{minor}" for major, minor in PREFERRED_PYTHON_VERSIONS
    }

    assert expected_classifiers <= classifiers


def test_optional_publication_imports_stay_explicitly_declared_integrations() -> None:
    repo_root = _repo_root()
    project = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    dependencies: list[str] = project["dependencies"]
    optional = project.get("optional-dependencies", {})
    runtime_requirement_names = _normalized_dependency_names(dependencies)
    optional_extras_by_dependency = _optional_dependency_extras(optional)

    assert _optional_import_locations(repo_root, set(_OPTIONAL_IMPORT_MODULE_TO_DEPENDENCY)) == (
        _EXPECTED_OPTIONAL_IMPORT_LOCATIONS
    )

    for module_name, dependency_name in _OPTIONAL_IMPORT_MODULE_TO_DEPENDENCY.items():
        assert dependency_name not in runtime_requirement_names
        assert module_name in _EXPECTED_OPTIONAL_IMPORT_LOCATIONS
        assert _EXPECTED_OPTIONAL_DEPENDENCY_EXTRAS[dependency_name] <= optional_extras_by_dependency[dependency_name]

    bridge_constants = _string_constant_assignments(repo_root, "src/gpd/mcp/servers/arxiv_bridge.py")
    assert bridge_constants["UPSTREAM_ARXIV_MODULE"] == "arxiv_mcp_server"
    assert "arxiv-mcp-server" not in runtime_requirement_names
    assert _EXPECTED_OPTIONAL_DEPENDENCY_EXTRAS["arxiv-mcp-server"] <= optional_extras_by_dependency["arxiv-mcp-server"]


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


def test_model_visible_command_note_does_not_depend_on_live_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    import gpd.core.model_visible_text as model_visible_text
    import gpd.registry as registry

    def _raise_registry_error() -> tuple[str, ...]:
        raise RuntimeError("registry agent parse failed")

    monkeypatch.setattr(registry, "list_agents", _raise_registry_error)

    note = model_visible_text.command_visibility_note()

    assert "`agent` must match a built-in canonical agent label exactly" in note
    assert "gpd-planner" not in note


def test_infra_descriptors_reference_public_bootstrap_flow() -> None:
    from gpd.mcp.builtin_servers import build_public_descriptors

    repo_root = _repo_root()
    stale_markers = (
        "packages/gpd",
        "uv pip install -e",
        "pip install -e packages/gpd",
        _SHARED_INSTALL.bootstrap_command,
    )
    expected_descriptors = build_public_descriptors()

    for path in sorted((repo_root / "infra").glob("gpd-*.json")):
        content = path.read_text(encoding="utf-8")
        assert _PUBLIC_BOOTSTRAP_PREREQUISITE in content, f"{path.name} should reference the public prerequisite flow"
        for marker in stale_markers:
            assert marker not in content, f"{path.name} should not mention {marker!r}"
        assert json.loads(content) == expected_descriptors[path.stem]

    assert {path.stem for path in (repo_root / "infra").glob("gpd-*.json")} == set(expected_descriptors)


def test_public_gpd_infra_descriptors_use_entry_points_not_python() -> None:
    repo_root = _repo_root()

    for path in sorted((repo_root / "infra").glob("gpd-*.json")):
        descriptor = json.loads(path.read_text(encoding="utf-8"))
        assert descriptor["command"].startswith("gpd-mcp-")
        assert descriptor["args"] == []


def test_gitignore_covers_repo_local_npm_cache() -> None:
    repo_root = _repo_root()
    assert ".npm-cache/" in (repo_root / ".gitignore").read_text(encoding="utf-8")


def test_gitignore_covers_repo_local_uv_cache_and_test_reports() -> None:
    repo_root = _repo_root()
    content = (repo_root / ".gitignore").read_text(encoding="utf-8")

    assert ".uv-cache/" in content
    assert ".tox/" in content
    assert ".nox/" in content
    assert ".coverage" in content
    assert ".coverage.*" in content
    assert "coverage.xml" in content
    assert "htmlcov/" in content
    assert "junit.xml" in content
    assert "pytest-report.xml" in content
    assert "*.prof" in content
    assert "*.profraw" in content
    assert "*.profdata" in content


def test_gitignore_covers_repo_local_tmp_root() -> None:
    repo_root = _repo_root()
    content = (repo_root / ".gitignore").read_text(encoding="utf-8")

    assert "tmp/" in content


def test_gitignore_covers_local_gpd_fix_reports() -> None:
    repo_root = _repo_root()
    content = (repo_root / ".gitignore").read_text(encoding="utf-8")

    assert "GPD-FIX-REPORT-*.md" in content
    assert "GPD-FIX-REPORT*/" in content


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
    ignored_patterns = {line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")}
    for pattern in ("GPD/", "GPD/*", "GPD/STATE.md", "GPD/state.json"):
        assert pattern not in ignored_patterns, f".gitignore must not contain {pattern!r}"


def test_gitignore_only_excludes_specific_repo_root_gpd_state_noise(tmp_path: Path) -> None:
    """State lock/backup files are local crash-recovery noise, not project docs."""
    repo_root = _repo_root()
    init_test_git_repo(tmp_path)
    (tmp_path / ".gitignore").write_text((repo_root / ".gitignore").read_text(encoding="utf-8"), encoding="utf-8")

    ignored = ("GPD/state.json.bak", "GPD/state.json.lock")
    visible = ("GPD/state.json", "GPD/STATE.md", "GPD/phases/notes.md", "other/GPD/state.json.lock")

    for relpath in (*ignored, *visible):
        path = tmp_path / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("local state\n", encoding="utf-8")

    for relpath in ignored:
        result = run_git(
            tmp_path,
            "check-ignore",
            "--quiet",
            "--",
            relpath,
            check=False,
        )
        assert result.returncode == 0, f"{relpath} should be ignored"

    for relpath in visible:
        result = run_git(
            tmp_path,
            "check-ignore",
            "--quiet",
            "--",
            relpath,
            check=False,
        )
        assert result.returncode == 1, f"{relpath} should stay visible to git"


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
    init_test_git_repo(tmp_path, user_name="Test", user_email="test@test.com")

    # Seed an initial commit so HEAD exists.
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    git_add(tmp_path, "README.md")
    git_commit(tmp_path, "init")

    # Stage a GPD file and a non-GPD file.
    gpd_dir = tmp_path / "GPD"
    gpd_dir.mkdir()
    (gpd_dir / "STATE.md").write_text("state\n", encoding="utf-8")
    (tmp_path / "real.txt").write_text("real\n", encoding="utf-8")
    git_add(tmp_path, "GPD/STATE.md", "real.txt")

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
    staged = run_git(tmp_path, "diff", "--cached", "--name-only")
    staged_files = staged.stdout.strip().splitlines()
    assert "real.txt" in staged_files
    assert "GPD/STATE.md" not in staged_files


def test_human_author_check_rejects_lowercase_codex_coauthor_in_range(tmp_path: Path) -> None:
    repo_root = _repo_root()
    hook_script = repo_root / "scripts" / "check-human-authors.sh"

    init_test_git_repo(tmp_path)
    seed_test_git_repo(tmp_path)

    (tmp_path / "README.md").write_text("seed\nchange\n", encoding="utf-8")
    git_add(tmp_path, "README.md")
    git_commit(tmp_path, "change", extra_message="co-authored-by: Codex")

    result = subprocess.run(
        ["sh", str(hook_script), "--range", "HEAD~1..HEAD"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "non-human commit attribution found" in result.stderr
    assert "co-author trailer: co-authored-by: Codex" in result.stderr
    assert "change" in result.stderr


def test_human_author_check_rejects_nonhuman_author_and_committer_in_range(tmp_path: Path) -> None:
    repo_root = _repo_root()
    hook_script = repo_root / "scripts" / "check-human-authors.sh"

    init_test_git_repo(tmp_path)
    seed_test_git_repo(tmp_path)

    (tmp_path / "README.md").write_text("seed\nchange\n", encoding="utf-8")
    git_add(tmp_path, "README.md")
    git_commit(
        tmp_path,
        "ai attributed",
        env=git_identity_env(
            author_name="Codex Bot",
            author_email="codex@example.com",
            committer_name="Copilot Bot",
            committer_email="copilot@example.com",
        ),
    )

    result = subprocess.run(
        ["sh", str(hook_script), "--range", "HEAD~1..HEAD"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "author: Codex Bot <codex@example.com>" in result.stderr
    assert "committer: Copilot Bot <copilot@example.com>" in result.stderr


def test_human_author_check_allows_explicit_repository_automation_identities(tmp_path: Path) -> None:
    repo_root = _repo_root()
    hook_script = repo_root / "scripts" / "check-human-authors.sh"
    dependabot_config = yaml.safe_load((repo_root / ".github" / "dependabot.yml").read_text(encoding="utf-8"))

    assert dependabot_config["updates"], "Dependabot remains enabled, so its exact bot identity must be allowed"

    init_test_git_repo(tmp_path)
    seed_test_git_repo(tmp_path)

    (tmp_path / "README.md").write_text("seed\nrelease\n", encoding="utf-8")
    git_add(tmp_path, "README.md")
    git_commit(
        tmp_path,
        "release: v9.9.9",
        env=git_identity_env(
            author_name="github-actions[bot]",
            author_email="41898282+github-actions[bot]@users.noreply.github.com",
        ),
    )

    (tmp_path / "README.md").write_text("seed\nrelease\ndependabot\n", encoding="utf-8")
    git_add(tmp_path, "README.md")
    git_commit(
        tmp_path,
        "build(deps): bump actions/setup-python from 5 to 6",
        env=git_identity_env(
            author_name="dependabot[bot]",
            author_email="49699333+dependabot[bot]@users.noreply.github.com",
        ),
    )

    (tmp_path / "README.md").write_text("seed\nrelease\ndependabot\nmerge\n", encoding="utf-8")
    git_add(tmp_path, "README.md")
    git_commit(
        tmp_path,
        "Merge pull request #999 from psi-oss/release/v9.9.9",
        env=git_identity_env(
            author_name="Human Author",
            author_email="human@example.com",
            committer_name="GitHub",
            committer_email="noreply@github.com",
        ),
    )

    result = subprocess.run(
        ["sh", str(hook_script), "--range", "HEAD~3..HEAD"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Human author attribution check passed" in result.stdout


def test_human_author_commit_msg_hook_rejects_nonhuman_current_identity(tmp_path: Path) -> None:
    repo_root = _repo_root()
    hook_script = repo_root / "scripts" / "check-human-authors.sh"

    init_test_git_repo(tmp_path, user_name="Codex Bot", user_email="codex@example.com")
    message_path = tmp_path / "COMMIT_EDITMSG"
    message_path.write_text("change\n", encoding="utf-8")

    result = subprocess.run(
        ["sh", str(hook_script), str(message_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "non-human commit attribution detected" in result.stderr
    assert "author: Codex Bot <codex@example.com>" in result.stderr


def test_human_author_check_fails_closed_on_invalid_range(tmp_path: Path) -> None:
    repo_root = _repo_root()
    hook_script = repo_root / "scripts" / "check-human-authors.sh"

    init_test_git_repo(tmp_path)
    seed_test_git_repo(tmp_path)

    result = subprocess.run(
        ["sh", str(hook_script), "--range", "missing-base..HEAD"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "invalid git range missing-base..HEAD" in result.stderr


def test_release_test_checkout_fixture_copies_only_tracked_files(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    checkout_root = tmp_path / "checkout"
    source_root.mkdir()

    init_test_git_repo(source_root)

    (source_root / ".gitignore").write_text("ignored-artifact.txt\n", encoding="utf-8")
    (source_root / "tracked.txt").write_text("tracked from working tree\n", encoding="utf-8")
    (source_root / "nested").mkdir()
    (source_root / "nested" / "tracked.py").write_text("print('tracked')\n", encoding="utf-8")
    git_add(source_root, ".gitignore", "tracked.txt", "nested/tracked.py")
    (source_root / "untracked-artifact.txt").write_text("untracked\n", encoding="utf-8")
    (source_root / "ignored-artifact.txt").write_text("ignored\n", encoding="utf-8")

    _copy_checkout_for_release_test(source_root, checkout_root)

    assert (checkout_root / "tracked.txt").read_text(encoding="utf-8") == "tracked from working tree\n"
    assert (checkout_root / "nested" / "tracked.py").is_file()
    assert not (checkout_root / ".git").exists()
    assert not (checkout_root / "untracked-artifact.txt").exists()
    assert not (checkout_root / "ignored-artifact.txt").exists()


def test_npm_pack_dry_run_uses_temp_cache_outside_repo(tmp_path: Path) -> None:
    repo_root = _repo_root()
    if shutil.which("npm") is None:
        pytest.skip("npm is not available")

    repo_cache = repo_root / ".npm-cache"
    existed_before = repo_cache.exists()
    before_paths = (
        sorted(path.relative_to(repo_cache).as_posix() for path in repo_cache.rglob("*")) if existed_before else []
    )

    pack = _npm_pack_dry_run(repo_root, tmp_path)
    packed_paths = _packaged_file_paths(pack)

    assert pack["name"] == "get-physics-done"
    assert pack["version"] == _python_release_version(repo_root)
    assert packed_paths == {
        "LICENSE",
        "README.md",
        "bin/install.js",
        "package.json",
        *_BOOTSTRAP_JSON_ASSETS,
    }
    readme_links = _readme_relative_file_links((repo_root / "README.md").read_text(encoding="utf-8"))
    missing_readme_links = sorted(readme_links - packed_paths)
    assert not missing_readme_links, (
        "README local links must either be absolute or ship in the npm package:\n"
        + "\n".join(f"- {path}" for path in missing_readme_links)
    )
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
        (build_root / ".tox" / "py312" / "gpd-sdist-hygiene-leak.txt", b"tox"),
        (build_root / ".nox" / "tests" / "gpd-sdist-hygiene-leak.txt", b"nox"),
        (build_root / "htmlcov" / "index.html", b"coverage"),
        (build_root / ".coverage", b"coverage"),
        (build_root / ".coverage.local", b"coverage"),
        (build_root / "coverage.xml", b"coverage"),
        (build_root / "junit.xml", b"junit"),
        (build_root / "pytest-report.xml", b"pytest"),
        (build_root / "profile.prof", b"profile"),
        (build_root / "coverage.profraw", b"profile"),
        (build_root / "coverage.profdata", b"profile"),
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
        ".coverage",
        ".mypy_cache/",
        ".nox/",
        ".npm-cache/",
        ".pytest_cache/",
        ".ruff_cache/",
        ".tox/",
        ".uv-cache/",
        ".venv/",
        ".egg-info/",
        ".prof",
        ".profdata",
        ".profraw",
        ".pyc",
        ".pyo",
        "/build/",
        "/coverage.xml",
        "/GPD-FIX-REPORT",
        "/htmlcov/",
        "/junit.xml",
        "/pytest-report.xml",
        "/dist/",
        "/tmp/",
    )
    assert not [name for name in sorted(names) if any(fragment in name for fragment in forbidden_fragments)]


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
    assert not [name for name in sorted(names) if any(fragment in name for fragment in forbidden_fragments)]


def test_prepare_release_updates_all_versioned_public_surfaces(tmp_path: Path) -> None:
    repo_root = _repo_root()
    _copy_release_surfaces(repo_root, tmp_path)
    current_version = _python_release_version(repo_root)
    next_version = bump_version(current_version, "patch")
    original_citation = (tmp_path / "CITATION.cff").read_text(encoding="utf-8")
    original_readme = (tmp_path / "README.md").read_text(encoding="utf-8")

    changelog_path = tmp_path / "CHANGELOG.md"
    changelog_path.write_text(
        (repo_root / "CHANGELOG.md")
        .read_text(encoding="utf-8")
        .replace(
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
    original_year_match = re.search(r"^  year = \{(\d{4})\},\s*$", original_readme, re.M)
    assert original_year_match is not None
    original_year = original_year_match.group(1)

    assert f"version = {{{next_version}}}" in readme
    assert f"(Version {next_version})" in readme
    assert f"year = {{{original_year}}}" in readme
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
