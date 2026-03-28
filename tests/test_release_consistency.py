"""Guardrails for public release consistency."""

from __future__ import annotations

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

from gpd.adapters import get_adapter
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.core.surface_phrases import (
    cost_after_runs_guidance,
    cost_summary_surface_note,
    local_cli_bridge_note,
    recovery_ladder_note,
    workflow_preset_storage_note,
)
from scripts.release_workflow import (
    ReleaseError,
    bump_version,
    extract_release_notes,
    prepare_release,
    stamp_publish_date,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


_RUNTIME_DESCRIPTORS = iter_runtime_descriptors()


def _documented_runtime_flags() -> tuple[str, ...]:
    flags: set[str] = set()
    for descriptor in _RUNTIME_DESCRIPTORS:
        flags.update(descriptor.selection_flags)
    return tuple(sorted(flags))


def _runtime_note_heading_regex(descriptor) -> re.Pattern[str]:
    display_name = re.escape(descriptor.display_name)
    short_name = re.escape(descriptor.display_name.split()[0])
    if display_name == short_name:
        return re.compile(rf"{display_name}-specific note:")
    return re.compile(rf"(?:{display_name}|{short_name})-specific note:")


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


def _copy_release_surfaces(repo_root: Path, out_dir: Path) -> None:
    for relative_path in ("CHANGELOG.md", "CITATION.cff", "README.md", "package.json", "pyproject.toml"):
        shutil.copy2(repo_root / relative_path, out_dir / relative_path)


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


HELP_COMMAND_HEADING_RE = re.compile(r"^\*\*`/gpd:([a-z0-9-]+)(?:[^`]*)`\*\*$", re.MULTILINE)
README_COMMAND_ROW_RE = re.compile(r"^\| `/gpd:([a-z0-9-]+)(?:[^`]*)` \| (.*?) \|$", re.MULTILINE)
DOCTOR_RUNTIME_SCOPE_RE = re.compile(r"gpd doctor --runtime <runtime> --local\|--global")
UNATTENDED_READINESS_SURFACE = "gpd validate unattended-readiness"
PERMISSIONS_SYNC_SURFACE = "gpd permissions sync --runtime <runtime> --autonomy balanced"
PLAN_PREFLIGHT_SURFACE = "gpd validate plan-preflight <PLAN.md>"
WOLFRAM_STATUS_SURFACE = "gpd integrations status wolfram"


def _assert_unattended_readiness_surface(content: str) -> None:
    assert UNATTENDED_READINESS_SURFACE in content
    assert PERMISSIONS_SYNC_SURFACE in content
    assert "gpd doctor" in content
    assert (
        "runtime-owned approval/alignment only" in content
        or "runtime-owned permission alignment" in content
        or "Runtime permissions are" in content
    )


def _assert_shared_preset_surface_contract(content: str) -> None:
    assert workflow_preset_storage_note() in content or (
        "existing config keys" in content or "bundles over the existing config keys only" in content
    )
    assert "gpd presets list" in content
    assert "gpd presets show <preset>" in content
    assert "gpd presets apply <preset> --dry-run" in content or "gpd presets apply <preset>" in content


def _assert_cost_advisory_contract(content: str) -> None:
    assert "gpd cost" in content
    assert "current profile tier mix" in content
    assert "advisory only" in content or "billing truth" in content
    assert "partial or estimated rather than exact" in content or "estimated rather than exact" in content


def _assert_wolfram_plan_boundary(content: str) -> None:
    assert WOLFRAM_STATUS_SURFACE in content
    assert PLAN_PREFLIGHT_SURFACE in content
    assert (
        "does not prove local Mathematica availability or plan readiness" in content
        or "does not mean a plan is ready to run" in content
        or "shared Wolfram integration surface" in content
        or "shared optional Wolfram integration config" in content
        or "does not install Mathematica or prove plan readiness" in content
    )


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


def _command_inventory_stems(repo_root: Path) -> set[str]:
    return {path.stem for path in (repo_root / "src/gpd/commands").glob("*.md")}


def _help_heading_stems(content: str) -> set[str]:
    return set(HELP_COMMAND_HEADING_RE.findall(content))


def _readme_command_rows(content: str) -> dict[str, str]:
    return {stem: description.strip() for stem, description in README_COMMAND_ROW_RE.findall(content)}


def _markdown_section(content: str, heading: str) -> str:
    lines = content.splitlines()
    collected: list[str] = []
    in_section = False
    for line in lines:
        if line == heading:
            in_section = True
        elif in_section and line.startswith("## "):
            break
        if in_section:
            collected.append(line)
    assert collected, f"expected section {heading!r}"
    return "\n".join(collected)


def _extract_between(content: str, start_marker: str, end_marker: str) -> str:
    start = content.index(start_marker)
    end = content.index(end_marker, start)
    return content[start:end]


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
    assert 'const GITHUB_MAIN_BRANCH = "main"' in content
    assert "installManagedPackage(managedEnv.python, pythonPackageVersion" in content
    assert "archive/refs/tags/v${version}.tar.gz" in content
    assert "archive/refs/heads/${GITHUB_MAIN_BRANCH}.tar.gz" in content
    assert "git+${repoGitUrl}@v${version}" in content
    assert "git+${repoGitUrl}@${GITHUB_MAIN_BRANCH}" in content
    assert "function repositoryGitUrl(" in content
    assert "function repositorySshGitUrl(" not in content
    assert "requestedVersion" in content
    assert "GitHub sources" in content


def test_public_bootstrap_installer_documents_public_flags_and_runtime_aliases() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    content = (repo_root / "bin" / "install.js").read_text(encoding="utf-8")

    assert "npx -y get-physics-done" in readme
    for flag in _documented_runtime_flags():
        assert f"`{flag}`" in readme
    assert "`--all`" in readme
    assert "`--global`" in readme
    assert "`--local`" in readme
    assert "`-g`" in readme
    assert "`-l`" in readme
    assert (
        "Override the runtime config directory; defaults to local scope unless the path resolves to that runtime's canonical global config dir."
        in readme
    )
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
    assert "~/GPD/venv" in readme
    assert "latest GitHub `main` source" in readme
    assert "github:psi-oss/get-physics-done --upgrade" in readme
    assert "--reinstall" in content
    assert "--upgrade" in content
    assert "Reinstall the matching tagged GitHub source in ~/GPD/venv" in content
    assert "Upgrade ~/GPD/venv from the latest GitHub main source" in content


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
    assert "~/GPD/venv/bin/gpd uninstall" not in readme
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
    assert '"gpt-5.4"' in readme
    assert '"gpt-5.4-mini"' in readme
    assert '"gpt-5.4-nano"' in readme
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
        assert "~/GPD/venv" in content

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
    assert "actions/checkout@v5" in workflow
    assert "actions/setup-python@v6" in workflow
    assert 'python-version: "3.11"' in workflow
    assert "astral-sh/setup-uv@v7" in workflow
    assert "uv sync --dev" in workflow
    assert "uv run pytest tests/ -v" in workflow


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
    assert "actions/checkout@v5" in workflow
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
    assert "environment:" in workflow
    assert "name: PyPI" in workflow
    assert "id-token: write" in workflow
    assert "actions/checkout@v5" in workflow
    assert "actions/setup-python@v6" in workflow
    assert "actions/setup-node@v6" in workflow
    assert "actions/upload-artifact@v6" in workflow
    assert "actions/download-artifact@v8" in workflow
    assert "pypa/gh-action-pypi-publish@release/v1" in workflow
    assert "npm publish" in workflow
    assert "gh release create" in workflow
    assert "post-release/v${VERSION}-publish-date" in workflow
    assert "ref: ${{ needs.build-release.outputs.release_sha }}" in workflow
    assert "scripts/release_workflow.py release-notes" in workflow
    assert "gh pr create" in workflow


def test_public_docs_keep_runtime_surface_first() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")

    assert "## Quick Start" in readme
    assert "## Supported Runtimes" in readme
    assert "## Advanced CLI Utilities" in readme
    assert readme.index("## Supported Runtimes") < readme.index("## Advanced CLI Utilities")
    assert "## Known Limitations" in readme
    assert "After installing GPD, open your chosen runtime normally" in readme
    assert "Observability and trace inspection" in readme
    assert "GPD/observability/" in readme
    assert "`GPD/STATE.md` | Concise human-readable continuity state" in readme
    assert "does not fabricate opaque provider internals" in readme


def test_public_readme_quick_start_keeps_runtime_first_next_steps() -> None:
    readme = (_repo_root() / "README.md").read_text(encoding="utf-8")
    quick_start = _markdown_section(readme, "## Quick Start")

    assert "npx -y get-physics-done" in quick_start
    assert "The bootstrap installer requires Node.js 20+, Python 3.11+ with `venv`" in quick_start
    assert "**Next steps after install**" in quick_start
    assert "The installer adds GPD to your runtime config" in quick_start
    assert "it does not launch the runtime for you" in quick_start
    assert "Open your chosen runtime from your normal system terminal" in quick_start
    assert "Run its help command first: Claude Code / Gemini CLI use `/gpd:help`" in quick_start
    assert "Codex uses `$gpd-help`, and OpenCode uses `/gpd-help`." in quick_start
    assert "For best performance, run both this install step and your chosen runtime" in quick_start
    assert "`claude` for Claude Code" in quick_start
    assert "`gemini` for Gemini CLI" in quick_start
    assert "/gpd:help" in quick_start
    assert "$gpd-help" in quick_start
    assert "/gpd-help" in quick_start


def test_public_help_default_quick_start_keeps_runtime_surface_readiness_path() -> None:
    help_command = (_repo_root() / "src/gpd/commands/help.md").read_text(encoding="utf-8")
    quick_start = _extract_between(
        help_command,
        "## Step 2: Quick Start (Default Output)",
        "## Step 3: Full Command Reference (--all)",
    )

    assert "Choose the path that matches your starting point:" in quick_start
    assert "**New work**" in quick_start
    assert "**Existing work**" in quick_start
    assert "**Returning work**" in quick_start
    assert "**Tangents**" in quick_start
    assert "**Local CLI bridge**" in quick_start
    assert "**Unattended / autonomy setup**" in quick_start
    assert "/gpd:new-project" in quick_start
    assert "/gpd:new-project --minimal" in quick_start
    assert "/gpd:map-research" in quick_start
    assert "/gpd:resume-work" in quick_start
    assert "gpd resume --recent" in quick_start
    assert "gpd --help" in quick_start
    assert UNATTENDED_READINESS_SURFACE in quick_start
    assert PERMISSIONS_SYNC_SURFACE in quick_start
    assert "/gpd:progress" in quick_start
    assert "/gpd:suggest-next" in quick_start
    assert "gpd cost" in quick_start
    assert "/gpd:tangent" in quick_start
    assert "/gpd:settings" in quick_start
    assert "/gpd:help --all" in quick_start
    assert "**Core workflow:**" in quick_start
    assert "**Publication:**" in quick_start
    assert "canonical in-runtime slash-command names" in quick_start
    assert "not a promise that the local `gpd` CLI exposes matching top-level subcommands." in quick_start
    assert "## Invocation Surfaces" not in quick_start


def test_public_help_surfaces_keep_publication_workflows_visible_for_optional_add_ons() -> None:
    repo_root = _repo_root()
    help_command = (repo_root / "src/gpd/commands/help.md").read_text(encoding="utf-8")
    help_workflow = (repo_root / "src/gpd/specs/workflows/help.md").read_text(encoding="utf-8")

    assert "**Publication:** write-paper → peer-review → respond-to-referees → arxiv-submission" in help_command
    for content in (help_command, help_workflow):
        assert "**`/gpd:write-paper [title or topic] [--from-phases 1,2,3]`**" in content
        assert "**`/gpd:arxiv-submission`**" in content
        assert "Drafts the manuscript and uses `gpd paper-build` for the canonical scaffold/build contract" in content
        assert "Prepare a completed paper for arXiv submission with validation and packaging." in content


def test_public_readme_quick_start_surfaces_step_one_entry_points() -> None:
    readme = (_repo_root() / "README.md").read_text(encoding="utf-8")
    quick_start = _markdown_section(readme, "## Quick Start")

    assert "The table below uses the Claude Code / Gemini CLI form for in-runtime commands." in quick_start
    assert "Codex and OpenCode use the equivalent prefixed forms" in quick_start
    assert "`gpd ...` rows are local terminal commands." in quick_start
    assert "| New research project | `/gpd:new-project` |" in quick_start
    assert "| New research project, fast path | `/gpd:new-project --minimal` |" in quick_start
    assert "| Current-workspace recovery snapshot | `gpd resume` |" in quick_start
    assert "| Continue in an existing GPD project | `/gpd:resume-work` |" in quick_start
    assert "| Existing research folder or codebase | `/gpd:map-research` |" in quick_start
    assert "gpd resume --recent" in quick_start
    assert "gpd --help" in quick_start
    assert UNATTENDED_READINESS_SURFACE in quick_start
    assert PERMISSIONS_SYNC_SURFACE in quick_start
    assert "Guided unattended configuration path: use your runtime-specific `settings` command after startup" in quick_start
    assert "use your runtime-specific `tangent` command when GPD surfaces an alternative path worth checking" in quick_start
    assert "`tangent` is the lightweight chooser for stay / quick / defer / branch" in quick_start
    assert "the matching `branch-hypothesis` command only when you want the explicit git-backed alternative path" in quick_start
    assert "For model choice, the safe default is `review` plus runtime defaults." in quick_start
    assert "Use your runtime-specific `settings` command to move toward `Max quality`, `Balanced`, or `Budget-aware`" in quick_start
    assert cost_after_runs_guidance().replace("local usage / cost", "local usage/cost") in quick_start
    assert "Use the exact runtime-specific command syntax below for your first command." in quick_start
    assert "If you are starting from existing work, run your runtime's `map-research` command first" in quick_start
    assert "gpd cost" in quick_start
    assert "/gpd:new-project --minimal" in quick_start
    assert "$gpd-resume-work" in quick_start
    assert "/gpd:map-research" in quick_start
    assert recovery_ladder_note(
        resume_work_phrase="the runtime `resume-work` command",
        suggest_next_phrase="the runtime `suggest-next` command",
        pause_work_phrase="your runtime-specific `pause-work` command",
    ) in quick_start
    assert "| Continue in an existing GPD project | `/gpd:resume-work` | Use the runtime `resume-work` command to continue from the selected project state. |" in quick_start


def test_public_readme_quick_start_keeps_settings_guided_balanced_unattended_readiness_path() -> None:
    readme = (_repo_root() / "README.md").read_text(encoding="utf-8")
    quick_start = _markdown_section(readme, "## Quick Start")

    assert "For unattended execution, the recommended default is Balanced (`balanced`)." in quick_start
    assert "Use your runtime-specific `settings` command to confirm or change autonomy" in quick_start
    _assert_unattended_readiness_surface(quick_start)
    assert "executable probes" in quick_start
    assert "pdflatex" in quick_start
    assert "wolframscript" in quick_start
    assert f"Local CLI bridge: {local_cli_bridge_note()}" in quick_start
    assert "Balanced (`balanced`) is the recommended unattended default." in quick_start
    assert UNATTENDED_READINESS_SURFACE in quick_start
    assert (
        "If it returns `relaunch-required`, exit and relaunch the runtime before treating unattended use as ready."
    ) in quick_start


def test_public_readme_and_bootstrap_surface_optional_workflow_add_on_guidance() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    installer = (repo_root / "bin/install.js").read_text(encoding="utf-8")

    _assert_cost_advisory_contract(readme)
    _assert_unattended_readiness_surface(readme)
    _assert_wolfram_plan_boundary(readme)
    assert "executable probes" in readme
    _assert_shared_preset_surface_contract(readme)
    assert "gpd doctor --runtime <runtime> --local|--global" in readme
    assert "paper-toolchain readiness" in readme
    assert "Missing preset tooling degrades that preset; it does not block the base GPD install." in readme
    assert "gpd doctor --runtime <runtime> --local|--global" in readme
    assert "plan to use that preset" in readme or "plan paper/manuscript workflows" in readme
    assert "degraded readiness for `write-paper`" in readme
    assert "Use `gpd paper-build` to judge whether the manuscript scaffold is buildable." in readme
    assert WOLFRAM_STATUS_SURFACE in readme
    assert PLAN_PREFLIGHT_SURFACE in readme
    assert "Workflow presets: if you plan paper/manuscript workflows, rerun " in installer
    assert (
        "Use `gpd doctor` for install and runtime-local readiness, `gpd validate unattended-readiness` for the unattended "
        "or overnight verdict, and `gpd permissions ...` for runtime-owned permission alignment and sync."
    ) in installer
    assert "check whether `Workflow Presets` is `ready` or `degraded`." in installer
    assert "Without LaTeX, the paper/manuscript and full research presets remain usable for `write-paper` and `peer-review`" in installer
    assert "`paper-build` and `arxiv-submission` require the `LaTeX Toolchain`." in installer


def test_public_paper_toolchain_capability_model_stays_consistent_across_surfaces() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    help_command = (repo_root / "src/gpd/commands/help.md").read_text(encoding="utf-8")
    help_workflow = (repo_root / "src/gpd/specs/workflows/help.md").read_text(encoding="utf-8")
    installer = (repo_root / "bin/install.js").read_text(encoding="utf-8")

    readme_preset_degrade_snippet = "Missing preset tooling degrades that preset; it does not block the base GPD install."
    help_preset_snippet = "Paper/manuscript workflows"
    installer_readiness_snippet = (
        "Use `gpd doctor` for install and runtime-local readiness, `gpd validate unattended-readiness` for the unattended "
        "or overnight verdict, and `gpd permissions ...` for runtime-owned permission alignment and sync."
    )
    _assert_unattended_readiness_surface(readme)
    _assert_wolfram_plan_boundary(readme)
    for content in (help_command, help_workflow):
        _assert_unattended_readiness_surface(content)
        _assert_wolfram_plan_boundary(content)
    assert installer_readiness_snippet in installer
    _assert_shared_preset_surface_contract(readme)
    assert readme_preset_degrade_snippet in readme
    _assert_cost_advisory_contract(readme)
    assert WOLFRAM_STATUS_SURFACE in readme
    assert "shared Wolfram integration" in readme
    assert "Local Mathematica installs are separate from the shared optional Wolfram integration config." in help_command
    assert "Local Mathematica installs are separate from the shared optional Wolfram integration config." in help_workflow
    for content in (help_command, help_workflow):
        assert help_preset_snippet in content
        assert "paper-toolchain readiness" in content
        assert "degrade `write-paper`" in content
        assert "`paper-build` remains the build contract" in content
        assert "`arxiv-submission` requires the built manuscript" in content
        assert DOCTOR_RUNTIME_SCOPE_RE.search(content) is not None
        assert WOLFRAM_STATUS_SURFACE in content
    assert "Workflow presets: if you plan paper/manuscript workflows, rerun " in installer
    assert "check whether `Workflow Presets` is `ready` or `degraded`." in installer
    assert "Without LaTeX, the paper/manuscript and full research presets remain usable for `write-paper` and `peer-review`" in installer
    assert "but `paper-build` and `arxiv-submission` require the `LaTeX Toolchain`." in installer


def test_public_readme_keeps_bootstrap_prerequisites_and_runtime_doctor_scopes_distinct() -> None:
    readme = (_repo_root() / "README.md").read_text(encoding="utf-8")
    quick_start = _markdown_section(readme, "## Quick Start")

    assert "The bootstrap installer requires Node.js 20+, Python 3.11+ with `venv`" in quick_start
    assert "**Bootstrap hard blockers**" in quick_start
    assert "These are bootstrap prerequisites for `npx -y get-physics-done`, not a claim that every local `gpd ...` command rechecks them." in quick_start
    assert "Here, `gpd doctor --runtime ...` is a runtime-readiness check for the selected runtime target." in quick_start
    _assert_unattended_readiness_surface(quick_start)
    _assert_wolfram_plan_boundary(quick_start)
    assert DOCTOR_RUNTIME_SCOPE_RE.search(quick_start) is not None
    _assert_shared_preset_surface_contract(quick_start)
    assert WOLFRAM_STATUS_SURFACE in quick_start
    assert (
        "If the bootstrap installer fails before `gpd doctor --runtime <runtime> --local|--global` can run, "
        "fix Node / Python / `venv` bootstrap prerequisites first."
    ) in quick_start
    assert (
        "If `gpd doctor --runtime <runtime> --local|--global` fails, fix the selected runtime's launcher / target / "
        "runtime-readiness issue first."
    ) in quick_start
    assert (
        "If `gpd doctor --runtime <runtime> --local|--global` only warns about `Workflow Presets` or `LaTeX Toolchain`, "
        "the base install can still be fine; treat that as degraded readiness for `write-paper` and local smoke checks "
        "rather than a full install blocker. If you pass `--live-executable-probes`, doctor may also report missing local tools "
        "like `pdflatex` or `wolframscript`; that still stays separate from `gpd integrations status wolfram` and from "
        "`gpd validate plan-preflight <PLAN.md>`. Use `gpd paper-build` to judge whether the manuscript scaffold is buildable."
    ) in quick_start


def test_public_readme_recovery_surfaces_keep_runtime_pause_and_resume_roles_distinct() -> None:
    readme = (_repo_root() / "README.md").read_text(encoding="utf-8")
    quick_start = _markdown_section(readme, "## Quick Start")

    assert "| Current-workspace recovery snapshot | `gpd resume` |" in quick_start
    assert "| Continue in an existing GPD project | `/gpd:resume-work` |" in quick_start
    assert "| Returning to an existing GPD project | `pause-work` |" not in quick_start
    assert "use `gpd resume`" in quick_start
    assert "gpd resume --recent" in quick_start
    assert "| Returning to an existing GPD project | `/gpd:resume-work` | `$gpd-resume-work` | `/gpd-resume-work` |" in readme
    assert "#### Session Management" in readme
    assert "| `/gpd:resume-work` | Resume research from the previous session with full context restoration |" in readme
    assert "| `/gpd:pause-work` | Create a context handoff when pausing research mid-phase |" in readme
    assert "gpd resume --recent" in readme


def test_public_readme_and_help_surfaces_keep_tangent_discoverable() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    help_command = (repo_root / "src/gpd/commands/help.md").read_text(encoding="utf-8")
    help_workflow = (repo_root / "src/gpd/specs/workflows/help.md").read_text(encoding="utf-8")

    assert "#### Tangents & Hypothesis Branches" in readme
    assert re.search(r"\| `/gpd:tangent(?: [^`]*)?` \| .*?(?:tangent|side investigation|alternative direction|parallel)", readme, re.I)
    assert re.search(r"\*\*`/gpd:tangent(?: [^`]*)?`\*\*", help_command)
    assert re.search(r"\*\*`/gpd:tangent(?: [^`]*)?`\*\*", help_workflow)
    assert "Chooser for stay / quick / defer / branch" in help_command
    assert "Chooser for stay / quick / defer / branch" in help_workflow


def test_public_readme_and_help_keep_tangent_vs_branch_taxonomy_explicit() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    help_command = (repo_root / "src/gpd/commands/help.md").read_text(encoding="utf-8")
    help_workflow = (repo_root / "src/gpd/specs/workflows/help.md").read_text(encoding="utf-8")

    assert "Use the matching `branch-hypothesis` command only when you want the explicit git-backed alternative path" in readme
    assert "route it through the runtime `tangent` command first" in readme
    for content in (help_command, help_workflow):
        assert "If `gpd observe execution` surfaces an alternative-path follow-up" in content
        assert "Keeps hypothesis branching as an explicit follow-on decision rather than the default for every tangent" in content
        assert "Explicit git-backed alternative path" in content


def test_public_help_surfaces_keep_settings_as_guided_post_startup_path() -> None:
    repo_root = _repo_root()
    help_command = (repo_root / "src/gpd/commands/help.md").read_text(encoding="utf-8")
    help_workflow = (repo_root / "src/gpd/specs/workflows/help.md").read_text(encoding="utf-8")

    for content in (help_command, help_workflow):
        assert "3. `/gpd:settings` - Primary guided unattended/autonomy setup after project creation" in content
        assert "Paper/manuscript workflows" in content
        _assert_shared_preset_surface_contract(content)
        _assert_cost_advisory_contract(content)
        assert "gpd --help" in content
        _assert_unattended_readiness_surface(content)
        assert "paper-toolchain readiness" in content
        assert "executable probes" in content
        assert "degrade `write-paper`" in content
        assert "`paper-build` remains the build contract" in content
        assert "`arxiv-submission` requires the built manuscript" in content
        assert "gpd observe execution" in content
        assert "The bootstrap installer owns Node.js / Python / `venv` prerequisites." in content


def test_public_settings_workflow_keeps_balanced_recommendation_and_relaunch_guidance() -> None:
    settings_workflow = (_repo_root() / "src/gpd/specs/workflows/settings.md").read_text(encoding="utf-8")

    assert '`autonomy` -- human-in-the-loop level: `"supervised"`, `"balanced"` (default), `"yolo"`' in settings_workflow
    assert (
        '{ label: "Balanced (Recommended)", description: "Best default for most unattended runs. '
        'AI handles routine work and pauses on important physics decisions, ambiguities, blockers, or scope changes." }'
    ) in settings_workflow
    assert 'gpd --raw permissions sync --autonomy "$SELECTED_AUTONOMY"' in settings_workflow
    assert "If `requires_relaunch` is `true`, surface `next_step` verbatim" in settings_workflow
    assert "Runtime permissions sync attempted after autonomy is written, with relaunch guidance surfaced when required" in settings_workflow
    assert "This sync only updates runtime-owned permission settings; it does not validate install health or workflow/tool readiness." in settings_workflow
    _assert_shared_preset_surface_contract(settings_workflow)
    assert UNATTENDED_READINESS_SURFACE in settings_workflow
    assert f"Local CLI bridge: {local_cli_bridge_note()}" in settings_workflow
    _assert_wolfram_plan_boundary(settings_workflow)
    assert "What model-cost posture should GPD optimize for?" in settings_workflow
    assert "Use runtime defaults" in settings_workflow
    assert cost_after_runs_guidance() in settings_workflow
    assert f"Local CLI bridge: {local_cli_bridge_note()}" in settings_workflow


def test_public_bootstrap_help_examples_cover_install_and_readiness_handoff() -> None:
    content = (_repo_root() / "bin/install.js").read_text(encoding="utf-8")

    assert "[install|uninstall] [options]" in content
    assert "# Interactive install" in content
    assert "# Install for all runtimes globally" in content
    assert "# Install into an explicit local target directory" in content
    assert "# Reinstall the matching managed GitHub source" in content
    assert "# Upgrade to the latest GitHub main source" in content
    assert "# Interactive uninstall" in content
    assert "# Uninstall from all runtimes globally" in content
    assert "# Equivalent uninstall subcommand form" in content
    assert "Use the runtime-specific `settings` command after startup to review autonomy, workflow defaults, and model-cost posture." in content
    assert "Recommended unattended default: Balanced autonomy (`balanced`). The safest model starting point is `review` plus runtime defaults." in content


def test_public_readme_observability_surface_keeps_execution_guidance_in_command_space() -> None:
    readme = (_repo_root() / "README.md").read_text(encoding="utf-8")

    assert "Observability and trace inspection" in readme
    assert "| `gpd observe sessions [--status ...] [--command ...] [--last N]` | List recorded observability sessions |" in readme
    assert "| `gpd observe show [--session ...] [--category ...] [--name ...] [--action ...] [--status ...] [--command ...] [--phase ...] [--plan ...] [--last N]` | Show logged observability events with filters |" in readme
    assert "| `gpd observe event <category> <name> [--action ...] [--status ...] [--command ...] [--phase ...] [--plan ...] [--session ...] [--data <json>]` | Append an explicit observability event with optional structured metadata |" in readme
    assert (
        "| `gpd observe execution` | Show read-only live execution status for the current workspace, including progress / waiting state, "
        "conservative `possibly stalled` wording, and the next read-only checks to run |"
    ) in readme
    assert "gpd observe execution" in readme
    assert "For read-only long-run visibility from your normal system terminal, use `gpd observe execution`." in readme
    assert "Start with `gpd observe show --last 20` when you need the recent event trail" in readme
    assert "route it through the runtime `tangent` command first" in readme
    _assert_cost_advisory_contract(readme)


def test_public_local_cli_help_and_install_summary_keep_readiness_diagnostics_emphasis() -> None:
    cli = (_repo_root() / "src/gpd/cli.py").read_text(encoding="utf-8")

    assert "local install, readiness, validation, permissions, observability, and diagnostics CLI" in cli
    assert "Use the local CLI for install, readiness checks, permissions, observability, validation, and diagnostics." in cli
    assert "gpd doctor --runtime <runtime> --local" in cli
    assert "gpd observe execution" in cli
    assert "gpd cost" in cli
    assert "gpd resume --recent" in cli
    assert "review autonomy, workflow defaults, and model-cost posture" in cli


def test_public_runtime_docs_explain_runtime_specific_command_syntax() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")

    assert "## Supported Runtimes" in readme
    for descriptor in _RUNTIME_DESCRIPTORS:
        adapter = get_adapter(descriptor.runtime_name)
        assert (
            f"| {descriptor.display_name} | `{descriptor.install_flag}` | "
            f"`{adapter.help_command}` | `{adapter.new_project_command}` |"
        ) in readme
    assert "Each runtime uses its own command prefix" in readme
    assert "Common first commands by runtime:" in readme


def test_codex_runtime_docs_distinguish_public_skills_from_full_agent_install() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")

    assert "Codex-specific note:" in readme
    assert "exposes only public `gpd-*` agents there as discoverable skills" in readme
    assert "the full agent catalog still installs under `.codex/agents/`" in readme


def test_public_runtime_notes_cover_all_runtime_specific_install_surfaces() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")

    for descriptor in _RUNTIME_DESCRIPTORS:
        assert _runtime_note_heading_regex(descriptor).search(readme) is not None
    assert "`policies/gpd-auto-edit.toml`" in readme
    assert "`CODEX_SKILLS_DIR`" in readme


def test_public_cli_docs_cover_project_contract_comparison_and_paper_build() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")

    assert "`gpd validate project-contract <file.json or -> [--mode approved|draft]`" in readme
    assert "| `/gpd:compare-results [phase, artifact, or comparison target]` |" in readme
    assert "`gpd paper-build [PAPER-CONFIG.json] [--output-dir <dir>]`" in readme


def test_public_readme_command_table_matches_command_inventory_and_regression_check_wording() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    inventory = _command_inventory_stems(repo_root)
    readme_rows = _readme_command_rows(readme)

    assert readme_rows, "expected README command table entries"
    assert set(readme_rows) == inventory
    assert (
        readme_rows["regression-check"]
        == "Scan-only audit for convention conflicts and verification-state regressions in completed phase summaries and verifications"
    )


def test_public_readme_typical_new_project_loop_includes_discuss_phase_before_planning() -> None:
    readme = (_repo_root() / "README.md").read_text(encoding="utf-8")

    assert "/gpd:new-project -> /gpd:discuss-phase 1 -> /gpd:plan-phase 1 -> /gpd:execute-phase 1 -> /gpd:verify-work 1" in readme
    assert "/gpd:new-project -> /gpd:plan-phase 1 -> /gpd:execute-phase 1 -> /gpd:verify-work 1" not in readme


def test_help_reference_surfaces_clarify_runtime_slash_commands_vs_local_cli() -> None:
    repo_root = _repo_root()
    help_command = (repo_root / "src/gpd/commands/help.md").read_text(encoding="utf-8")
    help_workflow = (repo_root / "src/gpd/specs/workflows/help.md").read_text(encoding="utf-8")

    required_snippets = (
        "`/gpd:*`",
        "in-runtime",
        "slash-command",
        "local `gpd` CLI",
        "gpd --help",
        UNATTENDED_READINESS_SURFACE,
        PERMISSIONS_SYNC_SURFACE,
        "gpd validate command-context gpd:<name>",
    )

    for snippet in required_snippets:
        assert snippet in help_command
        assert snippet in help_workflow


def test_help_reference_surfaces_keep_regression_check_wording_aligned_with_implementation() -> None:
    repo_root = _repo_root()
    help_command = (repo_root / "src/gpd/commands/help.md").read_text(encoding="utf-8")
    help_workflow = (repo_root / "src/gpd/specs/workflows/help.md").read_text(encoding="utf-8")

    for content in (help_command, help_workflow):
        assert "Scan-only" in content
        assert "SUMMARY" in content
        assert "frontmatter" in content
        assert "convention conflicts" in content
        assert "VERIFICATION" in content
        assert "canonical statuses" in content
        assert "re-runs dimensional analysis" not in content
        assert "re-runs limiting cases" not in content
        assert "re-runs numerical checks" not in content
        assert "re-verify" not in content


def test_help_reference_surfaces_match_command_inventory() -> None:
    repo_root = _repo_root()
    inventory = _command_inventory_stems(repo_root)
    help_command = (repo_root / "src/gpd/commands/help.md").read_text(encoding="utf-8")
    help_workflow = (repo_root / "src/gpd/specs/workflows/help.md").read_text(encoding="utf-8")

    command_help_stems = _help_heading_stems(help_command)
    workflow_help_stems = _help_heading_stems(help_workflow)

    assert command_help_stems == inventory
    assert workflow_help_stems == inventory


def test_regression_check_canonical_surfaces_match_scan_only_implementation() -> None:
    repo_root = _repo_root()
    command = (repo_root / "src/gpd/commands/regression-check.md").read_text(encoding="utf-8")
    workflow = (repo_root / "src/gpd/specs/workflows/regression-check.md").read_text(encoding="utf-8")
    transition = (repo_root / "src/gpd/specs/workflows/transition.md").read_text(encoding="utf-8")
    verify_work = (repo_root / "src/gpd/specs/workflows/verify-work.md").read_text(encoding="utf-8")

    for content in (command, workflow):
        assert "does **not** re-run physics, numerical, dimensional, or contract verification" in content
        assert "SUMMARY.md" in content
        assert "VERIFICATION.md" in content
        assert "convention_conflict" in content or "convention conflicts" in content
        assert "invalid_verification_status" in content or "invalid" in content
        assert "REGRESSION-REPORT.md" not in content
        assert "re-check verified targets" not in content
        assert "re-runs limiting cases" not in content

    assert "frontmatter" in transition
    assert "invalid verification statuses" in transition
    assert "/gpd:verify-work <phase>" in transition
    assert "| Result conflict |" not in transition

    assert "re-verify previously validated contract-backed outcomes" not in verify_work
    assert "SUMMARY.md" in verify_work
    assert "VERIFICATION.md" in verify_work
    assert "frontmatter" in verify_work


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
    assert optional == {"arxiv": ["arxiv-mcp-server>=0.3.2"]}





def test_infra_descriptors_reference_public_bootstrap_flow() -> None:
    from gpd.mcp.builtin_servers import build_public_descriptors

    repo_root = _repo_root()
    expected = "Install GPD before enabling built-in MCP servers."
    stale_markers = (
        "packages/gpd",
        "uv pip install -e",
        "pip install -e packages/gpd",
        "npx -y get-physics-done",
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
    assert "python scripts/sync_repo_graph_contract.py" in content
    assert "uv run python -m scripts.sync_repo_graph_contract" not in content
    assert "temporary cache outside the repo" in content
    assert "Public install docs should use `npx -y get-physics-done`." in content
    assert "Keep public artifacts present and up to date" in content
    assert "direct pushes are blocked" in content
    assert "required `tests` workflow" in content
    assert "Feature and fix PRs must not bump package versions or publish releases." in content
    assert "Add public release notes under `## vNEXT` in `CHANGELOG.md`" in content
    assert "## Release Process" not in content
    assert "`Prepare release`" not in content
    assert "`Publish release`" not in content


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
        assert _wheel_dependency_names(metadata) == _expected_wheel_dependency_names()

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
        assert 'const GITHUB_MAIN_BRANCH = "main"' in install_content
        assert '"-m", "venv"' in install_content
        assert '"GPD"' in install_content
        assert "archive/refs/tags/v${version}.tar.gz" in install_content
        assert "archive/refs/heads/${GITHUB_MAIN_BRANCH}.tar.gz" in install_content
        assert "git+${repoGitUrl}@v${version}" in install_content
        assert "git+${repoGitUrl}@${GITHUB_MAIN_BRANCH}" in install_content
        assert "requestedVersion" in install_content
        assert "GitHub sources" in install_content


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
