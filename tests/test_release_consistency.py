"""Guardrails for public release consistency."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest


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


def _python_release_version(repo_root: Path) -> str:
    package_json = json.loads((repo_root / "package.json").read_text(encoding="utf-8"))
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))

    package_version = str(package_json["version"])
    python_version = str(package_json["gpdPythonVersion"])
    pyproject_version = str(pyproject["project"]["version"])

    assert package_version == python_version == pyproject_version
    return pyproject_version


def _build_public_release_artifacts(repo_root: Path, out_dir: Path) -> tuple[Path, Path]:
    result = subprocess.run(
        ["uv", "build", "--out-dir", str(out_dir)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout

    wheel = next(out_dir.glob("get_physics_done-*.whl"))
    sdist = next(out_dir.glob("get_physics_done-*.tar.gz"))
    return wheel, sdist


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


def _paper_template_paths(repo_root: Path) -> tuple[list[str], list[str]]:
    template_root = repo_root / "src" / "gpd" / "mcp" / "paper" / "templates"
    relative_paths = sorted(path.relative_to(repo_root / "src").as_posix() for path in template_root.rglob("*_template.tex"))
    sdist_paths = [f"src/{path}" for path in relative_paths]
    return relative_paths, sdist_paths


def _expected_runtime_dependency_names() -> set[str]:
    return {
        "arxiv-mcp-server",
        "jinja2",
        "mcp",
        "pillow",
        "pybtex",
        "pydantic",
        "pyyaml",
        "rich",
        "typer",
    }


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


def test_public_citation_metadata_uses_launch_date() -> None:
    repo_root = _repo_root()
    citation = (repo_root / "CITATION.cff").read_text(encoding="utf-8")

    assert "date-released: '2026-03-15'" in citation


def test_public_citation_and_readme_versions_match_release_version() -> None:
    repo_root = _repo_root()
    version = _python_release_version(repo_root)
    citation = (repo_root / "CITATION.cff").read_text(encoding="utf-8")
    readme = (repo_root / "README.md").read_text(encoding="utf-8")

    assert f"version: {version}" in citation
    assert f"version = {{{version}}}" in readme
    assert f"(Version {version})" in readme


def test_public_docs_acknowledge_psi_and_gsd_inspiration() -> None:
    repo_root = _repo_root()

    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    assert "Physical Superintelligence PBC" in readme
    assert "GSD" in readme
    assert "get-shit-done" in readme
    assert "[Physical Superintelligence PBC (PSI)](https://www.psi.inc)" in readme


def test_public_metadata_records_psi_affiliation() -> None:
    repo_root = _repo_root()

    citation = (repo_root / "CITATION.cff").read_text(encoding="utf-8")
    contributing = (repo_root / "CONTRIBUTING.md").read_text(encoding="utf-8")
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))

    assert 'affiliation: "Physical Superintelligence PBC"' in citation
    assert "Physical Superintelligence PBC (PSI)" in contributing
    assert pyproject["project"]["authors"] == [{"name": "Physical Superintelligence PBC"}]
    assert pyproject["project"]["maintainers"] == [{"name": "Physical Superintelligence PBC"}]


def test_public_release_surfaces_share_copilot_positioning() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    package_json = json.loads((repo_root / "package.json").read_text(encoding="utf-8"))
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    installer = (repo_root / "bin" / "install.js").read_text(encoding="utf-8")

    expected = "open-source ai copilot for physics research"
    assert expected in readme.lower()
    assert expected in package_json["description"].lower()
    assert expected in pyproject["project"]["description"].lower()
    assert "Open-source AI copilot for physics research" in installer


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


def test_public_bootstrap_installer_pins_the_matching_python_release() -> None:
    repo_root = _repo_root()
    content = (repo_root / "bin" / "install.js").read_text(encoding="utf-8")

    assert 'require("../package.json")' in content
    assert "gpdPythonVersion" in content
    assert '["-m", "venv", "--help"]' in content
    assert "managed environment" in content
    assert 'const GITHUB_FALLBACK_BRANCH = "main"' in content
    assert "installManagedPackage(managedEnv.python, pythonPackageVersion" in content
    assert "archive/refs/tags/v${version}.tar.gz" in content
    assert "archive/refs/heads/${GITHUB_FALLBACK_BRANCH}.tar.gz" in content
    assert "git+${repoGitUrl}@v${version}" in content
    assert "git+${repoGitUrl}@${GITHUB_FALLBACK_BRANCH}" in content
    assert "function repositoryGitUrl(" in content
    assert "function repositorySshGitUrl(" not in content
    assert "requestedVersion" in content
    assert "GitHub sources" in content


def test_public_bootstrap_installer_documents_public_flags_and_runtime_aliases() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    content = (repo_root / "bin" / "install.js").read_text(encoding="utf-8")

    assert "npx -y get-physics-done" in readme
    assert "`--claude`" in readme
    assert "`--claude-code`" in readme
    assert "`--gemini`" in readme
    assert "`--gemini-cli`" in readme
    assert "`--codex`" in readme
    assert "`--opencode`" in readme
    assert "`--all`" in readme
    assert "`--global`" in readme
    assert "`--local`" in readme
    assert "`-g`" in readme
    assert "`-l`" in readme
    assert "`--target-dir <path>`" in readme
    assert "`--force-statusline`" in readme
    assert "`--help`" in readme
    assert "`-h`" in readme
    assert 'require("../src/gpd/adapters/runtime_catalog.json")' in content
    assert "runtimeInstallFlag(dollarCommandRuntime)" in content
    assert "runtimeConfigDirName(dollarCommandRuntime)" in content
    assert 'args.includes("--all")' in content
    assert 'documentedRuntimeFlags().join("/")' in content
    assert "runtimeSelectionFlags(runtime)" in content
    assert "runtimeSelectionAliases(runtime)" in content


def test_public_bootstrap_installer_documents_reinstall_and_upgrade_paths() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    content = (repo_root / "bin" / "install.js").read_text(encoding="utf-8")

    assert "`--reinstall`" in readme
    assert "`--upgrade`" in readme
    assert "~/.gpd/venv" in readme
    assert "latest GitHub `main` source" in readme
    assert "--reinstall" in content
    assert "--upgrade" in content
    assert "Reinstall the matching GitHub source in ~/.gpd/venv" in content
    assert "Upgrade ~/.gpd/venv from the latest GitHub main source" in content


def test_public_bootstrap_installer_documents_uninstall_path() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    content = (repo_root / "bin" / "install.js").read_text(encoding="utf-8")

    assert "## Uninstall" in readme
    assert "Run `npx -y get-physics-done --uninstall`" in readme
    assert "`--uninstall`" in readme
    assert "non-interactive uninstall" in readme
    assert "`--global`" in readme
    assert "`--local`" in readme
    assert "~/.gpd/venv/bin/gpd uninstall" not in readme
    assert "--uninstall" in content
    assert "Uninstall from selected runtime config" in content
    assert '--uninstall ${primaryFlag} --global' in content


def test_readme_documents_runtime_specific_tier_model_formats() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")

    assert "## Optional: Model Profiles And Tier Overrides" in readme
    assert "Runtime-specific model string examples" in readme
    assert "`opus`, `sonnet`, `haiku`" in readme
    assert "the exact string Codex accepts" in readme
    assert '"your-tier-1-codex-model"' in readme
    assert '"your-tier-1-gemini-model"' in readme
    assert "`provider/model`" in readme


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
    assert ".gpd/exports" not in workflow
    assert "Write files to `exports/`." in command
    assert "Files written to exports/" in command
    assert ".gpd/exports" not in command


def test_public_cli_surface_is_unified() -> None:
    repo_root = _repo_root()
    script_lines = _project_script_lines(repo_root)
    script_names = [line.split("=", 1)[0].strip().strip('"') for line in script_lines]

    assert 'gpd = "gpd.cli:entrypoint"' in script_lines
    assert all(name == "gpd" or name.startswith("gpd-mcp-") for name in script_names)
    assert sorted(path.name for path in (repo_root / "src" / "gpd").glob("cli*.py")) == ["cli.py"]


def test_install_docs_use_only_public_npx_flow() -> None:
    repo_root = _repo_root()
    npx_command = "npx -y get-physics-done"
    disallowed_markers = (
        "uv tool install",
        "python3 -m pip install",
        "gpd install",
    )

    for relative_path in ("README.md",):
        content = (repo_root / relative_path).read_text(encoding="utf-8")
        assert npx_command in content, f"{relative_path} should mention the npx bootstrap installer"
        for marker in disallowed_markers:
            assert marker not in content, f"{relative_path} should not mention {marker!r}"


def test_public_install_docs_list_bootstrap_prerequisites_and_current_layout() -> None:
    repo_root = _repo_root()

    for relative_path in ("README.md",):
        content = (repo_root / relative_path).read_text(encoding="utf-8")
        assert "Node.js with `npm`/`npx`" in content
        assert "Python 3.11+ with the standard `venv` module" in content
        assert "npm and GitHub" in content
        assert "~/.gpd/venv" in content

    assert not (repo_root / "docs" / "USER-GUIDE.md").exists()
    assert not (repo_root / "MANUAL-TEST-PLAN.md").exists()


def test_merge_gate_workflow_uses_main_branch_pytest_on_python_311() -> None:
    repo_root = _repo_root()
    workflow = (repo_root / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")

    assert "name: tests" in workflow
    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert "branches: [main]" in workflow
    assert "workflow_dispatch:" in workflow
    assert "name: pytest (3.11)" in workflow
    assert "actions/checkout@v4" in workflow
    assert "actions/setup-python@v5" in workflow
    assert 'python-version: "3.11"' in workflow
    assert "astral-sh/setup-uv@v4" in workflow
    assert "uv sync --dev" in workflow
    assert "uv run pytest tests/ -v" in workflow


def test_public_docs_keep_runtime_surface_first() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")

    assert "## Supported Runtimes" in readme
    assert "## Advanced CLI Utilities" in readme
    assert readme.index("## Supported Runtimes") < readme.index("## Advanced CLI Utilities")
    assert "## Known Limitations" in readme
    assert "After installing GPD, open your chosen runtime normally" in readme
    assert "Observability and trace inspection" in readme
    assert ".gpd/observability/" in readme
    assert "`STATE.md` | Concise human-readable continuity state" in readme
    assert "does not fabricate opaque provider internals" in readme


def test_public_runtime_docs_explain_runtime_specific_command_syntax() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")

    assert "## Supported Runtimes" in readme
    assert "| Claude Code | `--claude` | `/gpd:help` | `/gpd:new-project` |" in readme
    assert "| Gemini CLI | `--gemini` | `/gpd:help` | `/gpd:new-project` |" in readme
    assert "| Codex | `--codex` | `$gpd-help` | `$gpd-new-project` |" in readme
    assert "| OpenCode | `--opencode` | `/gpd-help` | `/gpd-new-project` |" in readme
    assert "Each runtime uses its own command prefix" in readme


def test_codex_runtime_docs_distinguish_public_skills_from_full_agent_install() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")

    assert "Codex-specific note:" in readme
    assert "exposes only public `gpd-*` agents there as discoverable skills" in readme
    assert "the full agent catalog still installs under `.codex/agents/`" in readme


def test_public_runtime_command_table_has_unique_entries() -> None:
    repo_root = _repo_root()
    lines = (repo_root / "README.md").read_text(encoding="utf-8").splitlines()

    in_table = False
    commands: list[str] = []
    for line in lines:
        if line == "## Key In-Runtime Commands":
            in_table = True
            continue
        if in_table and line.startswith("## "):
            break
        if not in_table or not line.startswith("| `"):
            continue
        command = line.split("`", 2)[1]
        commands.append(command)

    assert commands, "expected README key-command table entries"
    assert len(commands) == len(set(commands))


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
    assert optional == {}





def test_infra_descriptors_reference_public_bootstrap_flow() -> None:
    from gpd.mcp.builtin_servers import build_public_descriptors

    repo_root = _repo_root()
    expected = "npx -y get-physics-done"
    stale_markers = (
        "packages/gpd",
        "uv pip install -e",
        "pip install -e packages/gpd",
    )
    expected_descriptors = build_public_descriptors()

    for path in sorted((repo_root / "infra").glob("gpd-*.json")):
        content = path.read_text(encoding="utf-8")
        assert expected in content, f"{path.name} should reference the public bootstrap flow"
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
        if path.stem == "gpd-arxiv":
            assert descriptor["command"] == "python"
            continue

        assert descriptor["command"].startswith("gpd-mcp-")
        assert descriptor["args"] == []


def test_contributing_docs_cover_release_validation_flow() -> None:
    repo_root = _repo_root()
    content = (repo_root / "CONTRIBUTING.md").read_text(encoding="utf-8")

    assert "uv run pytest tests/test_release_consistency.py -v" in content
    assert "uv run pytest tests/adapters/test_registry.py tests/adapters/test_install_roundtrip.py -v" in content
    assert "Cross-runtime release checks:" in content
    assert 'npm_config_cache="$(mktemp -d)" npm pack --dry-run --json' in content
    assert "uv run python -m scripts.sync_repo_graph_contract" in content
    assert "temporary cache outside the repo" in content
    assert "Public install docs should use `npx -y get-physics-done`." in content
    assert "Keep public artifacts present and up to date" in content
    assert "direct pushes are blocked" in content
    assert "required `tests` workflow" in content


def test_gitignore_covers_repo_local_npm_cache() -> None:
    repo_root = _repo_root()
    assert ".npm-cache/" in (repo_root / ".gitignore").read_text(encoding="utf-8")


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
    packed_paths = {str(item["path"]) for item in pack["files"]}

    assert pack["name"] == "get-physics-done"
    assert pack["version"] == _python_release_version(repo_root)
    assert "bin/install.js" in packed_paths
    assert "src/gpd/adapters/runtime_catalog.json" in packed_paths
    assert (tmp_path / "npm-cache").is_dir()

    if existed_before:
        after_paths = sorted(path.relative_to(repo_cache).as_posix() for path in repo_cache.rglob("*"))
        assert after_paths == before_paths
    else:
        assert not repo_cache.exists()



def test_fresh_built_release_artifacts_match_public_bootstrap_and_docs(tmp_path: Path) -> None:
    repo_root = _repo_root()
    version = _python_release_version(repo_root)
    wheel, sdist = _build_public_release_artifacts(repo_root, tmp_path / "dist")
    wheel_template_paths, sdist_template_paths = _paper_template_paths(repo_root)

    assert wheel.name == f"get_physics_done-{version}-py3-none-any.whl"
    assert sdist.name == f"get_physics_done-{version}.tar.gz"

    with zipfile.ZipFile(wheel) as wheel_zip:
        wheel_names = set(wheel_zip.namelist())
        assert "gpd/cli.py" in wheel_names
        assert "gpd/mcp/viewer/cli.py" not in wheel_names
        for template_path in wheel_template_paths:
            assert template_path in wheel_names
        entry_points = wheel_zip.read(f"get_physics_done-{version}.dist-info/entry_points.txt").decode("utf-8")
        metadata = wheel_zip.read(f"get_physics_done-{version}.dist-info/METADATA").decode("utf-8")
        assert "gpd = gpd.cli:entrypoint" in entry_points
        assert _wheel_dependency_names(metadata) == _expected_runtime_dependency_names()

    sdist_prefix = f"get_physics_done-{version}/"
    with tarfile.open(sdist, "r:gz") as sdist_tar:
        sdist_names = set(sdist_tar.getnames())
        assert f"{sdist_prefix}README.md" in sdist_names
        assert f"{sdist_prefix}docs/USER-GUIDE.md" not in sdist_names
        assert f"{sdist_prefix}bin/install.js" in sdist_names
        assert f"{sdist_prefix}package.json" in sdist_names
        assert f"{sdist_prefix}MANUAL-TEST-PLAN.md" not in sdist_names
        for template_path in sdist_template_paths:
            assert f"{sdist_prefix}{template_path}" in sdist_names

        install_js = sdist_tar.extractfile(f"{sdist_prefix}bin/install.js")
        assert install_js is not None
        install_content = install_js.read().decode("utf-8")
        assert 'require("../package.json")' in install_content
        assert "gpdPythonVersion" in install_content
        assert 'const GITHUB_FALLBACK_BRANCH = "main"' in install_content
        assert '"-m", "venv"' in install_content
        assert '".gpd"' in install_content
        assert "archive/refs/tags/v${version}.tar.gz" in install_content
        assert "archive/refs/heads/${GITHUB_FALLBACK_BRANCH}.tar.gz" in install_content
        assert "git+${repoGitUrl}@v${version}" in install_content
        assert "git+${repoGitUrl}@${GITHUB_FALLBACK_BRANCH}" in install_content
        assert "requestedVersion" in install_content
        assert "GitHub sources" in install_content
