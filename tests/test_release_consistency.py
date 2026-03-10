"""Guardrails for public release consistency."""

from __future__ import annotations

import json
import subprocess
import tarfile
import tomllib
import zipfile
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


def _public_release_version(repo_root: Path) -> str:
    package_json = json.loads((repo_root / "package.json").read_text(encoding="utf-8"))
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))

    assert package_json["version"] == pyproject["project"]["version"]
    return str(package_json["version"])


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


def _paper_template_paths(repo_root: Path) -> tuple[list[str], list[str]]:
    template_root = repo_root / "src" / "gpd" / "mcp" / "paper" / "templates"
    relative_paths = sorted(path.relative_to(repo_root / "src").as_posix() for path in template_root.rglob("*_template.tex"))
    sdist_paths = [f"src/{path}" for path in relative_paths]
    return relative_paths, sdist_paths


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


def test_public_docs_acknowledge_psi_and_gsd_inspiration() -> None:
    repo_root = _repo_root()

    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    assert "Physical Superintelligence" in readme
    assert "GSD" in readme
    assert "get-shit-done-cc" in readme
    assert "[Physical Superintelligence](https://github.com/physicalsuperintelligence)" in readme


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
    assert '["-m", "venv", "--help"]' in content
    assert "managed environment" in content
    assert 'const PYTHON_PACKAGE_NAME = "get-physics-done"' in content
    assert 'const GITHUB_FALLBACK_BRANCH = "main"' in content
    assert "==${version}" in content
    assert "archive/refs/tags/v${version}.tar.gz" in content
    assert "archive/refs/heads/${GITHUB_FALLBACK_BRANCH}.tar.gz" in content
    assert "git+${repoGitUrl}@v${version}" in content
    assert "git+${repoGitUrl}@${GITHUB_FALLBACK_BRANCH}" in content
    assert "function repositoryGitUrl(" in content
    assert "git+ssh://git@github.com/physicalsuperintelligence/get-physics-done.git" not in content


def test_public_bootstrap_installer_accepts_documented_runtime_aliases() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    content = (repo_root / "bin" / "install.js").read_text(encoding="utf-8")

    assert "`--claude`" in readme
    assert "`--gemini`" in readme
    assert "`--codex`" in readme
    assert "`--opencode`" in readme
    assert "`--all`" in readme
    assert "npx -y get-physics-done --all --global" in readme
    assert "npx -y get-physics-done --codex --local" in content
    assert "npx -y get-physics-done --opencode --global" in content
    assert 'args.includes("--all")' in content
    assert 'args.includes("--claude")' in content
    assert 'args.includes("--gemini")' in content
    assert 'args.includes(`--${key}`)' in content
    assert '"codex": {' in content
    assert 'name: "Codex"' in content
    assert '"opencode": {' in content
    assert 'name: "OpenCode"' in content


def test_public_bootstrap_installer_documents_reinstall_and_upgrade_paths() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    content = (repo_root / "bin" / "install.js").read_text(encoding="utf-8")

    assert "`--reinstall`" in readme
    assert "`--upgrade`" in readme
    assert "npx -y get-physics-done --reinstall --claude --local" in readme
    assert "npx -y get-physics-done --upgrade --claude --local" in readme
    assert "--reinstall" in content
    assert "--upgrade" in content
    assert "Reinstall the matching Python release in ~/.gpd/venv" in content
    assert "Upgrade ~/.gpd/venv from the latest GitHub main source" in content


def test_public_bootstrap_installer_documents_uninstall_path() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    content = (repo_root / "bin" / "install.js").read_text(encoding="utf-8")

    assert "## Uninstall" in readme
    assert "npx -y get-physics-done --uninstall" in readme
    assert "npx -y get-physics-done --uninstall --claude --global" in readme
    assert "npx -y get-physics-done --uninstall --all --global" in readme
    assert "~/.gpd/venv/bin/gpd uninstall" not in readme
    assert "--uninstall" in content
    assert "Uninstall from selected runtime config" in content
    assert "npx -y get-physics-done --uninstall --claude --global" in content


def test_export_workflow_uses_release_attribution_footer() -> None:
    repo_root = _repo_root()
    content = (repo_root / "src" / "gpd" / "specs" / "workflows" / "export.md").read_text(encoding="utf-8")

    assert "<p><em>Generated with Get Physics Done (PSI)" in content
    assert "{\\footnotesize\\textit{Generated with Get Physics Done (PSI)}}" in content
    assert "Attribution: Generated with Get Physics Done (PSI)" in content
    assert "Tool: GPD (Get Physics Done)" not in content


def test_public_cli_surface_is_unified() -> None:
    repo_root = _repo_root()
    script_lines = _project_script_lines(repo_root)
    script_names = [line.split("=", 1)[0].strip().strip('"') for line in script_lines]

    assert 'gpd = "gpd.cli:app"' in script_lines
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
        assert "GitHub and PyPI" in content
        assert "~/.gpd/venv" in content

    assert not (repo_root / "docs" / "USER-GUIDE.md").exists()
    assert not (repo_root / "MANUAL-TEST-PLAN.md").exists()


def test_ci_workflow_uses_uv_locked_pytest_matrix() -> None:
    repo_root = _repo_root()
    workflow = (repo_root / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")

    assert "actions/checkout@v4" in workflow
    assert "actions/setup-python@v5" in workflow
    assert 'python-version: ["3.11", "3.12"]' in workflow
    assert "astral-sh/setup-uv@v4" in workflow
    assert "uv sync --dev" in workflow
    assert "uv run pytest tests/ -v" in workflow


def test_public_docs_keep_runtime_surface_first() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")

    assert "## Known Limitations" in readme
    assert "After installing GPD, open your chosen runtime normally" in readme
    assert "## Local Observability" in readme
    assert ".gpd/observability/" in readme
    assert "STATE.md: concise human-readable continuity state" in readme
    assert "fabricate opaque provider internals" in readme


def test_public_runtime_docs_explain_runtime_specific_command_syntax() -> None:
    repo_root = _repo_root()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")

    assert "Claude Code and Gemini CLI use `/gpd:...`" in readme
    assert "Codex installs `$gpd-...` skills" in readme
    assert "OpenCode uses `/gpd-...`" in readme
    assert "> /gpd:new-project        # Claude Code / Gemini CLI" in readme
    assert "> $gpd-new-project        # Codex" in readme
    assert "> /gpd-new-project        # OpenCode" in readme


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


def test_contributing_docs_cover_release_validation_flow() -> None:
    repo_root = _repo_root()
    content = (repo_root / "CONTRIBUTING.md").read_text(encoding="utf-8")

    assert "uv run pytest tests/test_release_consistency.py -v" in content
    assert "uv run pytest tests/adapters/test_registry.py tests/adapters/test_install_roundtrip.py -v" in content
    assert "Cross-runtime release checks:" in content
    assert "Public install docs should use `npx -y get-physics-done`." in content
    assert "Keep public artifacts present and up to date" in content



def test_fresh_built_release_artifacts_match_public_bootstrap_and_docs(tmp_path: Path) -> None:
    repo_root = _repo_root()
    version = _public_release_version(repo_root)
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
        assert "gpd = gpd.cli:app" in entry_points

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
        assert 'const PYTHON_PACKAGE_NAME = "get-physics-done"' in install_content
        assert 'const GITHUB_FALLBACK_BRANCH = "main"' in install_content
        assert "==${version}" in install_content
        assert '"-m", "venv"' in install_content
        assert '".gpd"' in install_content
        assert "archive/refs/tags/v${version}.tar.gz" in install_content
        assert "archive/refs/heads/${GITHUB_FALLBACK_BRANCH}.tar.gz" in install_content
        assert "git+${repoGitUrl}@v${version}" in install_content
        assert "git+${repoGitUrl}@${GITHUB_FALLBACK_BRANCH}" in install_content
