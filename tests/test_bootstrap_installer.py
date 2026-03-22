from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_JSON = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
PYPROJECT = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
PACKAGE_VERSION = str(PACKAGE_JSON["version"])
PYTHON_PACKAGE_VERSION = str(PACKAGE_JSON["gpdPythonVersion"])

REPO_GIT_URL = str(PACKAGE_JSON["repository"]["url"]).removeprefix("git+").rstrip("/")
if not REPO_GIT_URL.endswith(".git"):
    REPO_GIT_URL = f"{REPO_GIT_URL}.git"
REPO_BASE_URL = REPO_GIT_URL.removesuffix(".git")

PYPI_SPEC = f"get-physics-done=={PYTHON_PACKAGE_VERSION}"
TAG_ARCHIVE_SPEC = f"{REPO_BASE_URL}/archive/refs/tags/v{PYTHON_PACKAGE_VERSION}.tar.gz"
MAIN_ARCHIVE_SPEC = f"{REPO_BASE_URL}/archive/refs/heads/main.tar.gz"
TAG_HTTPS_GIT_SPEC = f"git+{REPO_GIT_URL}@v{PYTHON_PACKAGE_VERSION}"
MAIN_HTTPS_GIT_SPEC = f"git+{REPO_GIT_URL}@main"
RUNTIME_DISPLAY_NAMES = {
    "claude-code": "Claude Code",
    "codex": "Codex",
    "gemini": "Gemini CLI",
    "opencode": "OpenCode",
}
RUNTIME_HELP_COMMANDS = {
    "claude-code": "/gpd:help",
    "codex": "$gpd-help",
    "gemini": "/gpd:help",
    "opencode": "/gpd-help",
}
RUNTIME_LAUNCH_COMMANDS = {
    "claude-code": "claude",
    "codex": "codex",
    "gemini": "gemini",
    "opencode": "opencode",
}
RUNTIME_NEW_PROJECT_COMMANDS = {
    "claude-code": "/gpd:new-project",
    "codex": "$gpd-new-project",
    "gemini": "/gpd:new-project",
    "opencode": "/gpd-new-project",
}
RUNTIME_MAP_RESEARCH_COMMANDS = {
    "claude-code": "/gpd:map-research",
    "codex": "$gpd-map-research",
    "gemini": "/gpd:map-research",
    "opencode": "/gpd-map-research",
}
ALL_RUNTIME_NAMES = list(RUNTIME_DISPLAY_NAMES)


def test_version_consistency():
    """Release metadata and the bootstrap's Python pin must match."""
    assert PACKAGE_VERSION == PYTHON_PACKAGE_VERSION == str(PYPROJECT["project"]["version"])


def _write_fake_python(script_path: Path, log_path: Path, version_text: str = "Python 3.13.2") -> None:
    script = f"""#!{sys.executable}
import json
import os
import pathlib
import stat
import sys

LOG_PATH = pathlib.Path({str(log_path)!r})
FAIL_PYPI = os.environ.get("FAKE_PIP_FAIL_PYPI") == "1"
FAIL_TAG_ARCHIVE = os.environ.get("FAKE_PIP_FAIL_TAG_ARCHIVE") == "1"
FAIL_BRANCH_ARCHIVE = os.environ.get("FAKE_PIP_FAIL_BRANCH_ARCHIVE") == "1"
FAIL_TAG_GIT = os.environ.get("FAKE_PIP_FAIL_TAG_GIT") == "1"
FAIL_MAIN_GIT = os.environ.get("FAKE_PIP_FAIL_MAIN_GIT") == "1"
EMIT_PIP_SUCCESS_NOISE = os.environ.get("FAKE_PIP_SUCCESS_NOISE") == "1"
PYPI_SPEC = {PYPI_SPEC!r}
TAG_ARCHIVE_SPEC = {TAG_ARCHIVE_SPEC!r}
MAIN_ARCHIVE_SPEC = {MAIN_ARCHIVE_SPEC!r}
TAG_HTTPS_GIT_SPEC = {TAG_HTTPS_GIT_SPEC!r}
MAIN_HTTPS_GIT_SPEC = {MAIN_HTTPS_GIT_SPEC!r}
RUNTIME_LABELS = {RUNTIME_DISPLAY_NAMES!r}
LAUNCH_COMMANDS = {RUNTIME_LAUNCH_COMMANDS!r}
HELP_COMMANDS = {RUNTIME_HELP_COMMANDS!r}
NEW_PROJECT_COMMANDS = {RUNTIME_NEW_PROJECT_COMMANDS!r}
MAP_RESEARCH_COMMANDS = {RUNTIME_MAP_RESEARCH_COMMANDS!r}
ALL_RUNTIMES = {ALL_RUNTIME_NAMES!r}


def format_runtime_list(runtimes: list[str]) -> str:
    labels = [RUNTIME_LABELS[runtime] for runtime in runtimes]
    if not labels:
        return "no runtimes"
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{{labels[0]}} and {{labels[1]}}"
    return f"{{', '.join(labels[:-1])}}, and {{labels[-1]}}"


def selected_runtimes(argv: list[str]) -> list[str]:
    if "--all" in argv:
        return list(ALL_RUNTIMES)
    return [arg for arg in argv[3:] if arg in RUNTIME_LABELS]


def selected_scope(argv: list[str]) -> str:
    return "global" if "--global" in argv else "local"


def record() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {{
        "argv": sys.argv[1:],
        "exe": sys.argv[0],
        "managed": "venv" in pathlib.Path(sys.argv[0]).parts,
    }}
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\\n")


def write_managed_python(target: pathlib.Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(pathlib.Path(__file__).read_text(encoding="utf-8"), encoding="utf-8")
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


args = sys.argv[1:]

if args == ["--version"]:
    print({version_text!r})
    record()
    raise SystemExit(0)

if args == ["-m", "venv", "--help"]:
    print("usage: venv")
    record()
    raise SystemExit(0)

if args[:2] == ["-m", "venv"] and len(args) == 3:
    target = pathlib.Path(args[2])
    bin_dir = target / ("Scripts" if os.name == "nt" else "bin")
    for name in ("python", "python3"):
        write_managed_python(bin_dir / name)
    record()
    raise SystemExit(0)

if args == ["-m", "pip", "--version"] and "venv" not in pathlib.Path(sys.argv[0]).parts:
    record()
    raise SystemExit(1)

if args == ["-m", "pip", "--version"]:
    print("pip 26.0 from managed environment")
    record()
    raise SystemExit(0)

if args == ["-m", "ensurepip", "--upgrade"]:
    record()
    raise SystemExit(0)

if args[:4] == ["-m", "pip", "install", "--upgrade"]:
    target = args[-1]
    if FAIL_PYPI and target == PYPI_SPEC:
        record()
        sys.stderr.write("ERROR: No matching distribution found for get-physics-done\\n")
        raise SystemExit(1)
    if FAIL_TAG_ARCHIVE and target == TAG_ARCHIVE_SPEC:
        record()
        sys.stderr.write("ERROR: HTTP error 404 while getting tagged archive\\n")
        raise SystemExit(1)
    if FAIL_BRANCH_ARCHIVE and target == MAIN_ARCHIVE_SPEC:
        record()
        sys.stderr.write("ERROR: HTTP error 404 while getting branch archive\\n")
        raise SystemExit(1)
    if FAIL_TAG_GIT and target == TAG_HTTPS_GIT_SPEC:
        record()
        sys.stderr.write(f"ERROR: git checkout could not find tag v{PYTHON_PACKAGE_VERSION}\\n")
        raise SystemExit(1)
    if FAIL_MAIN_GIT and target == MAIN_HTTPS_GIT_SPEC:
        record()
        sys.stderr.write("ERROR: git checkout could not resolve branch main\\n")
        raise SystemExit(1)
    if EMIT_PIP_SUCCESS_NOISE:
        print("Requirement already satisfied: noisy-package==1.0.0")
    record()
    raise SystemExit(0)

if args[:3] == ["-m", "gpd.cli", "install"]:
    runtimes = selected_runtimes(args)
    scope = selected_scope(args)
    print(f"Installing GPD ({{scope}}) for: {{format_runtime_list(runtimes)}}")
    for runtime in runtimes:
        print(f"✓ {{RUNTIME_LABELS[runtime]}}")
    print("Install Summary")
    print("Next steps")
    if len(runtimes) == 1:
        runtime = runtimes[0]
        print(
            f"1. Open {{RUNTIME_LABELS[runtime]}} from your system terminal "
            f"({{LAUNCH_COMMANDS[runtime]}})."
        )
        print(f"2. Run {{HELP_COMMANDS[runtime]}} for the command list.")
        print(
            "3. Start with "
            f"{{NEW_PROJECT_COMMANDS[runtime]}} for a new project or "
            f"{{MAP_RESEARCH_COMMANDS[runtime]}} for existing work."
        )
    else:
        for runtime in runtimes:
            print(
                f"- {{RUNTIME_LABELS[runtime]}} ({{LAUNCH_COMMANDS[runtime]}}), then "
                f"{{HELP_COMMANDS[runtime]}}, then "
                f"{{NEW_PROJECT_COMMANDS[runtime]}} or {{MAP_RESEARCH_COMMANDS[runtime]}}"
            )
    record()
    raise SystemExit(0)

if args[:3] == ["-m", "gpd.cli", "uninstall"]:
    print("runtime uninstall ok")
    record()
    raise SystemExit(0)

record()
raise SystemExit(0)
"""
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(script, encoding="utf-8")
    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _run_bootstrap_with_fake_python(
    tmp_path: Path,
    *,
    installer_args: list[str] | None = None,
    extra_env: dict[str, str] | None = None,
    python_versions: dict[str, str] | None = None,
    precreate_managed_version: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    home = tmp_path / "home"
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir(parents=True)
    local_bin = home / ".local" / "bin"
    log_path = tmp_path / "python-log.jsonl"

    versions = {
        "python3.13": "Python 3.13.2",
        "python3.12": "Python 3.12.9",
        "python3.11": "Python 3.11.9",
        "python3": "Python 3.13.2",
        "python": "Python 3.13.2",
    }
    if python_versions:
        versions.update(python_versions)

    for name, version_text in versions.items():
        _write_fake_python(fake_bin / name, log_path, version_text)

    if precreate_managed_version is not None:
        managed_bin = home / ".gpd" / "venv" / "bin"
        for name in ("python", "python3"):
            _write_fake_python(managed_bin / name, log_path, precreate_managed_version)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["GPD_HOME"] = str(home / ".gpd")
    env["GPD_BOOTSTRAP_DISABLE_NETWORK_PROBES"] = "1"
    env["PATH"] = os.pathsep.join([str(local_bin), str(fake_bin), env.get("PATH", "")])
    if extra_env:
        env.update(extra_env)

    result = subprocess.run(
        ["node", "bin/install.js", *(installer_args or ["--codex", "--local"])],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    return result, home, log_path


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_uses_managed_virtualenv_and_skips_host_pip(tmp_path: Path) -> None:
    result, home, log_path = _run_bootstrap_with_fake_python(tmp_path)

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]

    assert any(entry["argv"] == ["-m", "venv", "--help"] for entry in entries)
    assert any(
        entry["argv"][:2] == ["-m", "venv"] and entry["argv"][-1].replace("\\", "/").endswith("/.gpd/venv")
        for entry in entries
    )

    base_pip_calls = [entry for entry in entries if not entry["managed"] and entry["argv"][:2] == ["-m", "pip"]]
    assert base_pip_calls == []

    managed_pip_installs = [
        entry for entry in entries if entry["managed"] and entry["argv"][:4] == ["-m", "pip", "install", "--upgrade"]
    ]
    assert len(managed_pip_installs) == 1
    assert "--quiet" in managed_pip_installs[0]["argv"]
    assert managed_pip_installs[0]["argv"][-1] == PYPI_SPEC

    managed_runtime_installs = [
        entry for entry in entries if entry["managed"] and entry["argv"] == ["-m", "gpd.cli", "install", "codex", "--local"]
    ]
    assert len(managed_runtime_installs) == 1

    assert (home / ".gpd" / "venv" / "bin" / "python").exists()
    assert f"GPD v{PACKAGE_VERSION} - Get Physics Done" in result.stdout
    assert "© 2026 Physical Superintelligence PBC (PSI)" in result.stdout
    assert "Installing GPD (local) for: Codex" in result.stdout
    assert "Install Summary" in result.stdout
    assert "Next steps" in result.stdout
    assert "1. Open Codex from your system terminal (codex)." in result.stdout
    assert "2. Run $gpd-help for the command list." in result.stdout
    assert (
        "3. Start with $gpd-new-project for a new project or $gpd-map-research for existing work."
        in result.stdout
    )
    assert "Installing GPD for Codex (local)..." not in result.stdout
    assert "Installed GPD for Codex (local)." not in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_uninstall_routes_to_runtime_uninstall(tmp_path: Path) -> None:
    result, home, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=["--uninstall", "--codex", "--local"],
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]

    assert any(entry["argv"] == ["-m", "venv", "--help"] for entry in entries)
    assert any(
        entry["argv"][:2] == ["-m", "venv"] and entry["argv"][-1].replace("\\", "/").endswith("/.gpd/venv")
        for entry in entries
    )

    managed_pip_installs = [
        entry for entry in entries if entry["managed"] and entry["argv"][:4] == ["-m", "pip", "install", "--upgrade"]
    ]
    assert len(managed_pip_installs) == 1
    assert managed_pip_installs[0]["argv"][-1] == PYPI_SPEC

    managed_runtime_uninstalls = [
        entry for entry in entries if entry["managed"] and entry["argv"] == ["-m", "gpd.cli", "uninstall", "codex", "--local"]
    ]
    assert len(managed_runtime_uninstalls) == 1

    assert (home / ".gpd" / "venv" / "bin" / "python").exists()
    assert f"Preparing managed GPD CLI from PyPI (get-physics-done=={PYTHON_PACKAGE_VERSION}) into the managed environment..." in result.stdout
    assert "Uninstalling GPD from Codex (local)..." in result.stdout
    assert "runtime uninstall ok" in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_uninstall_subcommand_alias_routes_to_runtime_uninstall(tmp_path: Path) -> None:
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=["uninstall", "--all", "--local"],
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    managed_runtime_uninstalls = [
        entry for entry in entries if entry["managed"] and entry["argv"] == ["-m", "gpd.cli", "uninstall", "--all", "--local"]
    ]

    assert len(managed_runtime_uninstalls) == 1
    assert "Claude Code" in result.stdout
    assert "Gemini CLI" in result.stdout
    assert "Codex" in result.stdout
    assert "OpenCode" in result.stdout
    assert "runtime uninstall ok" in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_install_subcommand_accepts_positional_runtime_alias(tmp_path: Path) -> None:
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=["install", "codex", "--local"],
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    managed_runtime_installs = [
        entry for entry in entries if entry["managed"] and entry["argv"] == ["-m", "gpd.cli", "install", "codex", "--local"]
    ]

    assert len(managed_runtime_installs) == 1
    assert "Installing GPD (local) for: Codex" in result.stdout
    assert "Install Summary" in result.stdout
    assert "Installed GPD for Codex (local)." not in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_supports_all_runtime_uninstall_in_one_pass(tmp_path: Path) -> None:
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=["--uninstall", "--all", "--global"],
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    managed_runtime_uninstalls = [
        entry for entry in entries if entry["managed"] and entry["argv"] == ["-m", "gpd.cli", "uninstall", "--all", "--global"]
    ]

    assert len(managed_runtime_uninstalls) == 1
    assert "Claude Code" in result.stdout
    assert "Gemini CLI" in result.stdout
    assert "Codex" in result.stdout
    assert "OpenCode" in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_uninstall_requires_explicit_runtime_non_interactively(tmp_path: Path) -> None:
    result, _, _ = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=["--uninstall", "--local"],
    )

    assert result.returncode == 1
    assert "Specify a runtime with" in result.stderr
    assert "or use --all when running --uninstall non-interactively." in result.stderr
    for flag in ("--claude", "--gemini", "--codex", "--opencode"):
        assert flag in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_uninstall_requires_explicit_scope_non_interactively(tmp_path: Path) -> None:
    result, _, _ = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=["--uninstall", "--codex"],
    )

    assert result.returncode == 1
    assert "Specify --global or --local when running --uninstall non-interactively." in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_uninstall_rejects_reinstall_flag(tmp_path: Path) -> None:
    result, _, _ = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=["--uninstall", "--codex", "--local", "--reinstall"],
    )

    assert result.returncode == 1
    assert "Cannot combine --uninstall with --reinstall." in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_rejects_reinstall_and_upgrade_together(tmp_path: Path) -> None:
    result, _, _ = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=["--codex", "--local", "--reinstall", "--upgrade"],
    )

    assert result.returncode == 1
    assert "Cannot combine --reinstall with --upgrade." in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_hides_successful_pip_chatter(tmp_path: Path) -> None:
    result, _, _ = _run_bootstrap_with_fake_python(
        tmp_path,
        extra_env={"FAKE_PIP_SUCCESS_NOISE": "1"},
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert "Requirement already satisfied: noisy-package==1.0.0" not in result.stdout
    assert "Install Summary" in result.stdout
    assert "Installed GPD for Codex (local)." not in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_forwards_target_dir_to_runtime_install(tmp_path: Path) -> None:
    target_dir = tmp_path / "custom target" / ".codex"
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=["--codex", "--local", "--target-dir", str(target_dir)],
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    managed_runtime_installs = [
        entry
        for entry in entries
        if entry["managed"]
        and entry["argv"] == ["-m", "gpd.cli", "install", "codex", "--local", "--target-dir", str(target_dir)]
    ]
    assert len(managed_runtime_installs) == 1


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_rejects_target_dir_with_all_runtimes(tmp_path: Path) -> None:
    target_dir = tmp_path / "custom target"
    result, _, _ = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=["--all", "--target-dir", str(target_dir)],
    )

    assert result.returncode == 1
    assert "--target-dir" in result.stderr
    assert "--all" in result.stderr
    assert "exactly one runtime" in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_reinstall_force_reinstalls_matching_release(tmp_path: Path) -> None:
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=["--codex", "--local", "--reinstall"],
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    managed_pip_installs = [
        entry for entry in entries if entry["managed"] and entry["argv"][:4] == ["-m", "pip", "install", "--upgrade"]
    ]

    assert len(managed_pip_installs) == 1
    assert "--force-reinstall" in managed_pip_installs[0]["argv"]
    assert managed_pip_installs[0]["argv"][-1] == PYPI_SPEC
    assert f"Reinstalling GPD from PyPI (get-physics-done=={PYTHON_PACKAGE_VERSION}) into the managed environment..." in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_upgrade_prefers_latest_main_source(tmp_path: Path) -> None:
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=["--claude", "--local", "--upgrade"],
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    managed_pip_installs = [
        entry for entry in entries if entry["managed"] and entry["argv"][:4] == ["-m", "pip", "install", "--upgrade"]
    ]

    assert len(managed_pip_installs) == 1
    assert "--force-reinstall" in managed_pip_installs[0]["argv"]
    assert "--no-cache-dir" in managed_pip_installs[0]["argv"]
    assert managed_pip_installs[0]["argv"][-1] == MAIN_ARCHIVE_SPEC
    assert "Upgrading GPD from the latest GitHub main branch into the managed environment..." in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_upgrade_falls_back_to_main_git_checkout(tmp_path: Path) -> None:
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=["--claude", "--local", "--upgrade"],
        extra_env={"FAKE_PIP_FAIL_BRANCH_ARCHIVE": "1"},
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    managed_pip_targets = [
        entry["argv"][-1] for entry in entries if entry["managed"] and entry["argv"][:4] == ["-m", "pip", "install", "--upgrade"]
    ]

    assert managed_pip_targets == [
        MAIN_ARCHIVE_SPEC,
        MAIN_HTTPS_GIT_SPEC,
    ]
    assert "current main branch source archive failed. Falling back to HTTPS git checkout of main..." in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_upgrade_prefers_preflighted_git_checkout_when_archive_is_inaccessible(tmp_path: Path) -> None:
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=["--claude", "--local", "--upgrade"],
        extra_env={
            "GPD_BOOTSTRAP_TEST_PROBES": json.dumps(
                {
                    MAIN_ARCHIVE_SPEC: {
                        "availability": "unavailable",
                        "reason": "HTTP 404",
                    },
                    MAIN_HTTPS_GIT_SPEC: {
                        "availability": "available",
                        "reason": "git ls-remote succeeded",
                    },
                }
            ),
        },
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    managed_pip_targets = [
        entry["argv"][-1] for entry in entries if entry["managed"] and entry["argv"][:4] == ["-m", "pip", "install", "--upgrade"]
    ]

    assert managed_pip_targets == [MAIN_HTTPS_GIT_SPEC]
    assert "Detected that current main branch source archive is unavailable: HTTP 404." in result.stdout
    assert "Using HTTPS git checkout of main for the main-branch upgrade." in result.stdout
    assert "HTTP error 404 while getting branch archive" not in result.stderr
    assert "current main branch source archive failed. Falling back to HTTPS git checkout of main..." not in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_upgrade_fails_closed_without_falling_back_to_release_sources(tmp_path: Path) -> None:
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=["--claude", "--local", "--upgrade"],
        extra_env={
            "FAKE_PIP_FAIL_BRANCH_ARCHIVE": "1",
            "FAKE_PIP_FAIL_MAIN_GIT": "1",
        },
    )

    assert result.returncode == 1

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    managed_pip_targets = [
        entry["argv"][-1] for entry in entries if entry["managed"] and entry["argv"][:4] == ["-m", "pip", "install", "--upgrade"]
    ]
    managed_runtime_installs = [
        entry for entry in entries if entry["managed"] and entry["argv"][:3] == ["-m", "gpd.cli", "install"]
    ]

    assert managed_pip_targets == [
        MAIN_ARCHIVE_SPEC,
        MAIN_HTTPS_GIT_SPEC,
    ]
    assert TAG_ARCHIVE_SPEC not in managed_pip_targets
    assert TAG_HTTPS_GIT_SPEC not in managed_pip_targets
    assert managed_runtime_installs == []
    assert "GitHub main upgrade failed across all main-branch candidates." in result.stdout
    assert "broader GitHub source candidate set" not in result.stdout
    assert f"Failed to install GPD v{PYTHON_PACKAGE_VERSION} from GitHub sources." in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_supports_all_runtime_install_in_one_pass(tmp_path: Path) -> None:
    result, _, log_path = _run_bootstrap_with_fake_python(tmp_path, installer_args=["--all", "--global"])

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    managed_runtime_installs = [
        entry for entry in entries if entry["managed"] and entry["argv"] == ["-m", "gpd.cli", "install", "--all", "--global"]
    ]

    assert len(managed_runtime_installs) == 1
    assert "Claude Code" in result.stdout
    assert "Gemini CLI" in result.stdout
    assert "Codex" in result.stdout
    assert "OpenCode" in result.stdout
    assert "Install Summary" in result.stdout
    assert "Next steps" in result.stdout
    assert "- Claude Code (claude), then /gpd:help, then /gpd:new-project or /gpd:map-research" in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_falls_back_to_tag_git_when_tag_archive_install_fails(tmp_path: Path) -> None:
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        extra_env={"FAKE_PIP_FAIL_PYPI": "1", "FAKE_PIP_FAIL_TAG_ARCHIVE": "1"},
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    managed_pip_targets = [
        entry["argv"][-1] for entry in entries if entry["managed"] and entry["argv"][:4] == ["-m", "pip", "install", "--upgrade"]
    ]

    assert managed_pip_targets == [
        PYPI_SPEC,
        TAG_ARCHIVE_SPEC,
        TAG_HTTPS_GIT_SPEC,
    ]
    assert "PyPI install failed. Falling back to GitHub source..." in result.stdout
    assert (
        f"GitHub source archive for v{PYTHON_PACKAGE_VERSION} failed. Falling back to HTTPS git checkout for v{PYTHON_PACKAGE_VERSION}..."
        in result.stdout
    )


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_prefers_preflighted_tag_git_candidate_when_tag_archive_is_inaccessible(tmp_path: Path) -> None:
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        extra_env={
            "FAKE_PIP_FAIL_PYPI": "1",
            "GPD_BOOTSTRAP_TEST_PROBES": json.dumps(
                {
                    TAG_ARCHIVE_SPEC: {
                        "availability": "unavailable",
                        "reason": "HTTP 404",
                    },
                    TAG_HTTPS_GIT_SPEC: {
                        "availability": "available",
                        "reason": "git ls-remote succeeded",
                    },
                }
            ),
        },
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    managed_pip_targets = [
        entry["argv"][-1] for entry in entries if entry["managed"] and entry["argv"][:4] == ["-m", "pip", "install", "--upgrade"]
    ]

    assert managed_pip_targets == [PYPI_SPEC, TAG_HTTPS_GIT_SPEC]
    assert "PyPI install failed. Falling back to GitHub source..." in result.stdout
    assert f"Detected that GitHub source archive for v{PYTHON_PACKAGE_VERSION} is unavailable: HTTP 404." in result.stdout
    assert f"Installing GPD from HTTPS git checkout for v{PYTHON_PACKAGE_VERSION} into the managed environment..." in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_release_install_fails_closed_without_falling_back_to_main_sources(tmp_path: Path) -> None:
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        extra_env={
            "FAKE_PIP_FAIL_PYPI": "1",
            "GPD_BOOTSTRAP_TEST_PROBES": json.dumps(
                {
                    TAG_ARCHIVE_SPEC: {
                        "availability": "unavailable",
                        "reason": "HTTP 404",
                    },
                    TAG_HTTPS_GIT_SPEC: {
                        "availability": "unavailable",
                        "reason": f"tag v{PYTHON_PACKAGE_VERSION} is not published",
                    },
                    MAIN_HTTPS_GIT_SPEC: {
                        "availability": "available",
                        "reason": "git ls-remote succeeded",
                    },
                }
            ),
        },
    )

    assert result.returncode == 1

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    managed_pip_installs = [
        entry for entry in entries if entry["managed"] and entry["argv"][:4] == ["-m", "pip", "install", "--upgrade"]
    ]

    assert len(managed_pip_installs) == 1  # PyPI attempted but failed
    assert f"Detected that GitHub source archive for v{PYTHON_PACKAGE_VERSION} is unavailable: HTTP 404." in result.stdout
    assert f"Detected that HTTPS git checkout for v{PYTHON_PACKAGE_VERSION} is unavailable: tag v{PYTHON_PACKAGE_VERSION} is not published." in result.stdout
    assert "No accessible tagged GitHub release source candidate was detected." in result.stdout
    assert "main branch" not in result.stdout
    assert f"Failed to install GPD v{PYTHON_PACKAGE_VERSION} from GitHub sources." in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_fails_closed_when_probes_mark_all_public_sources_unavailable(tmp_path: Path) -> None:
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        extra_env={
            "FAKE_PIP_FAIL_PYPI": "1",
            "GPD_BOOTSTRAP_TEST_PROBES": json.dumps(
                {
                    TAG_ARCHIVE_SPEC: {
                        "availability": "unavailable",
                        "reason": "HTTP 404",
                    },
                    TAG_HTTPS_GIT_SPEC: {
                        "availability": "unavailable",
                        "reason": "git exit 2",
                    },
                    MAIN_HTTPS_GIT_SPEC: {
                        "availability": "available",
                        "reason": "git ls-remote succeeded",
                    },
                }
            ),
        },
    )

    assert result.returncode == 1

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    managed_pip_installs = [
        entry for entry in entries if entry["managed"] and entry["argv"][:4] == ["-m", "pip", "install", "--upgrade"]
    ]

    assert len(managed_pip_installs) == 1  # PyPI attempted but failed
    assert f"Detected that GitHub source archive for v{PYTHON_PACKAGE_VERSION} is unavailable: HTTP 404." in result.stdout
    assert f"Detected that HTTPS git checkout for v{PYTHON_PACKAGE_VERSION} is unavailable: git exit 2." in result.stdout
    assert "No accessible tagged GitHub release source candidate was detected." in result.stdout
    assert "main branch" not in result.stdout
    assert f"Failed to install GPD v{PYTHON_PACKAGE_VERSION}" in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_fails_closed_when_all_release_sources_fail(tmp_path: Path) -> None:
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        extra_env={
            "FAKE_PIP_FAIL_PYPI": "1",
            "FAKE_PIP_FAIL_TAG_ARCHIVE": "1",
            "FAKE_PIP_FAIL_TAG_GIT": "1",
        },
    )

    assert result.returncode == 1

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    managed_pip_targets = [
        entry["argv"][-1] for entry in entries if entry["managed"] and entry["argv"][:4] == ["-m", "pip", "install", "--upgrade"]
    ]

    assert managed_pip_targets == [
        PYPI_SPEC,
        TAG_ARCHIVE_SPEC,
        TAG_HTTPS_GIT_SPEC,
    ]
    assert "current main branch source archive" not in result.stdout
    assert f"Failed to install GPD v{PYTHON_PACKAGE_VERSION} from GitHub sources." in result.stderr
    assert "Could not find a version that satisfies the requirement" not in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_prefers_versioned_python_when_generic_alias_is_newer(tmp_path: Path) -> None:
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        python_versions={
            "python3": "Python 3.14.3",
            "python": "Python 3.14.3",
            "python3.13": "Python 3.13.2",
        },
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    venv_creations = [
        entry for entry in entries if entry["argv"][:2] == ["-m", "venv"] and entry["argv"] != ["-m", "venv", "--help"]
    ]

    assert len(venv_creations) == 1
    assert venv_creations[0]["exe"].endswith("python3.13")
    assert "Found Python 3.13.2" in result.stdout
    assert "Found Python 3.14.3" not in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_recreates_managed_env_when_selected_minor_changes(tmp_path: Path) -> None:
    result, home, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        python_versions={
            "python3": "Python 3.14.3",
            "python": "Python 3.14.3",
            "python3.13": "Python 3.13.2",
        },
        precreate_managed_version="Python 3.14.3",
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    venv_creations = [
        entry for entry in entries if entry["argv"][:2] == ["-m", "venv"] and entry["argv"] != ["-m", "venv", "--help"]
    ]

    assert len(venv_creations) == 1
    assert venv_creations[0]["exe"].endswith("python3.13")
    assert "switching to Python 3.13.2" in result.stdout
    assert (home / ".gpd" / "venv" / "bin" / "python").exists()
