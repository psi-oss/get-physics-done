from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest


def _write_fake_python(script_path: Path, log_path: Path) -> None:
    script = f"""#!{sys.executable}
import json
import os
import pathlib
import stat
import sys

LOG_PATH = pathlib.Path({str(log_path)!r})
FAIL_PYPI_RELEASE = os.environ.get("FAKE_PIP_FAIL_PYPI") == "1"
FAIL_TAG_ARCHIVE = os.environ.get("FAKE_PIP_FAIL_TAG_ARCHIVE") == "1"
FAIL_BRANCH_ARCHIVE = os.environ.get("FAKE_PIP_FAIL_BRANCH_ARCHIVE") == "1"
FAIL_TAG_GIT = os.environ.get("FAKE_PIP_FAIL_TAG_GIT") == "1"
EMIT_PIP_SUCCESS_NOISE = os.environ.get("FAKE_PIP_SUCCESS_NOISE") == "1"


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
    print("Python 3.13.2")
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
    if FAIL_PYPI_RELEASE and target == "get-physics-done==0.1.0":
        record()
        sys.stderr.write("ERROR: Could not find a version that satisfies the requirement get-physics-done==0.1.0 (from versions: none)\\n")
        sys.stderr.write("ERROR: No matching distribution found for get-physics-done==0.1.0\\n")
        raise SystemExit(1)
    if FAIL_TAG_ARCHIVE and target.endswith("/archive/refs/tags/v0.1.0.tar.gz"):
        record()
        sys.stderr.write("ERROR: HTTP error 404 while getting tagged archive\\n")
        raise SystemExit(1)
    if FAIL_BRANCH_ARCHIVE and target.endswith("/archive/refs/heads/main.tar.gz"):
        record()
        sys.stderr.write("ERROR: HTTP error 404 while getting branch archive\\n")
        raise SystemExit(1)
    if FAIL_TAG_GIT and target.endswith(".git@v0.1.0"):
        record()
        sys.stderr.write("ERROR: git checkout could not find tag v0.1.0\\n")
        raise SystemExit(1)
    if EMIT_PIP_SUCCESS_NOISE:
        print("Requirement already satisfied: noisy-package==1.0.0")
    record()
    raise SystemExit(0)

if args[:3] == ["-m", "gpd.cli", "install"]:
    print("runtime install ok")
    record()
    raise SystemExit(0)

record()
raise SystemExit(0)
"""
    script_path.write_text(script, encoding="utf-8")
    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _run_bootstrap_with_fake_python(
    tmp_path: Path,
    *,
    installer_args: list[str] | None = None,
    extra_env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    repo_root = Path(__file__).resolve().parent.parent
    home = tmp_path / "home"
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir(parents=True)
    local_bin = home / ".local" / "bin"
    log_path = tmp_path / "python-log.jsonl"

    for name in ("python3", "python"):
        _write_fake_python(fake_bin / name, log_path)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["GPD_HOME"] = str(home / ".gpd")
    env["GPD_BOOTSTRAP_DISABLE_NETWORK_PROBES"] = "1"
    env["PATH"] = os.pathsep.join([str(local_bin), str(fake_bin), env.get("PATH", "")])
    if extra_env:
        env.update(extra_env)

    result = subprocess.run(
        ["node", "bin/install.js", *(installer_args or ["--codex", "--local"])],
        cwd=repo_root,
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
    assert managed_pip_installs[0]["argv"][-1] == "get-physics-done==0.1.0"

    managed_runtime_installs = [
        entry for entry in entries if entry["managed"] and entry["argv"] == ["-m", "gpd.cli", "install", "codex", "--local"]
    ]
    assert len(managed_runtime_installs) == 1

    assert (home / ".gpd" / "venv" / "bin" / "python").exists()
    assert "Installed GPD for Codex (local)." in result.stdout
    assert "$gpd-new-project" in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_hides_successful_pip_chatter(tmp_path: Path) -> None:
    result, _, _ = _run_bootstrap_with_fake_python(
        tmp_path,
        extra_env={"FAKE_PIP_SUCCESS_NOISE": "1"},
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert "Requirement already satisfied: noisy-package==1.0.0" not in result.stdout
    assert "Installed GPD for Codex (local)." in result.stdout


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
    assert managed_pip_installs[0]["argv"][-1] == "get-physics-done==0.1.0"
    assert "Reinstalling get-physics-done==0.1.0 into the managed environment..." in result.stdout


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
    assert (
        managed_pip_installs[0]["argv"][-1]
        == "https://github.com/physicalsuperintelligence/get-physics-done/archive/refs/heads/main.tar.gz"
    )
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
        "https://github.com/physicalsuperintelligence/get-physics-done/archive/refs/heads/main.tar.gz",
        "git+https://github.com/physicalsuperintelligence/get-physics-done.git@main",
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
                    "https://github.com/physicalsuperintelligence/get-physics-done/archive/refs/heads/main.tar.gz": {
                        "availability": "unavailable",
                        "reason": "HTTP 404",
                    },
                    "git+https://github.com/physicalsuperintelligence/get-physics-done.git@main": {
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

    assert managed_pip_targets == ["git+https://github.com/physicalsuperintelligence/get-physics-done.git@main"]
    assert "Detected that current main branch source archive is unavailable (HTTP 404)." in result.stdout
    assert "Using HTTPS git checkout of main for the main-branch upgrade." in result.stdout
    assert "HTTP error 404 while getting branch archive" not in result.stderr
    assert "current main branch source archive failed. Falling back to HTTPS git checkout of main..." not in result.stdout


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


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_falls_back_to_github_source_archives_when_pypi_release_is_missing(tmp_path: Path) -> None:
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
        "get-physics-done==0.1.0",
        "https://github.com/physicalsuperintelligence/get-physics-done/archive/refs/tags/v0.1.0.tar.gz",
        "https://github.com/physicalsuperintelligence/get-physics-done/archive/refs/heads/main.tar.gz",
    ]
    assert "PyPI install failed. Falling back to GitHub source archive for v0.1.0..." in result.stdout
    assert "GitHub source archive for v0.1.0 failed. Falling back to current main branch source archive..." in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_source_fallback_prefers_preflighted_git_candidate(tmp_path: Path) -> None:
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        extra_env={
            "FAKE_PIP_FAIL_PYPI": "1",
            "GPD_BOOTSTRAP_TEST_PROBES": json.dumps(
                {
                    "https://github.com/physicalsuperintelligence/get-physics-done/archive/refs/tags/v0.1.0.tar.gz": {
                        "availability": "unavailable",
                        "reason": "HTTP 404",
                    },
                    "https://github.com/physicalsuperintelligence/get-physics-done/archive/refs/heads/main.tar.gz": {
                        "availability": "unavailable",
                        "reason": "HTTP 404",
                    },
                    "git+https://github.com/physicalsuperintelligence/get-physics-done.git@v0.1.0": {
                        "availability": "unavailable",
                        "reason": "tag v0.1.0 is not published",
                    },
                    "git+https://github.com/physicalsuperintelligence/get-physics-done.git@main": {
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

    assert managed_pip_targets == [
        "get-physics-done==0.1.0",
        "git+https://github.com/physicalsuperintelligence/get-physics-done.git@main",
    ]
    assert "Detected that GitHub source archive for v0.1.0 is unavailable (HTTP 404)." in result.stdout
    assert "Detected that current main branch source archive is unavailable (HTTP 404)." in result.stdout
    assert "Detected that GitHub HTTPS git checkout for v0.1.0 is unavailable (tag v0.1.0 is not published)." in result.stdout
    assert "PyPI install failed. Using HTTPS git checkout of main." in result.stdout
    assert "HTTP error 404 while getting tagged archive" not in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_falls_back_to_authenticated_git_when_archive_urls_fail(tmp_path: Path) -> None:
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        extra_env={
            "FAKE_PIP_FAIL_PYPI": "1",
            "FAKE_PIP_FAIL_TAG_ARCHIVE": "1",
            "FAKE_PIP_FAIL_BRANCH_ARCHIVE": "1",
            "FAKE_PIP_FAIL_TAG_GIT": "1",
        },
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    managed_pip_targets = [
        entry["argv"][-1] for entry in entries if entry["managed"] and entry["argv"][:4] == ["-m", "pip", "install", "--upgrade"]
    ]

    assert managed_pip_targets == [
        "get-physics-done==0.1.0",
        "https://github.com/physicalsuperintelligence/get-physics-done/archive/refs/tags/v0.1.0.tar.gz",
        "https://github.com/physicalsuperintelligence/get-physics-done/archive/refs/heads/main.tar.gz",
        "git+https://github.com/physicalsuperintelligence/get-physics-done.git@v0.1.0",
        "git+https://github.com/physicalsuperintelligence/get-physics-done.git@main",
    ]
    assert (
        "current main branch source archive failed. Falling back to GitHub HTTPS git checkout for v0.1.0..."
        in result.stdout
    )
    assert "GitHub HTTPS git checkout for v0.1.0 failed. Falling back to HTTPS git checkout of main..." in result.stdout
