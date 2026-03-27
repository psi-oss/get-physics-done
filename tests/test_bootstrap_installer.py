from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from gpd.adapters import get_adapter, iter_runtime_descriptors

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
_RUNTIME_DESCRIPTORS = iter_runtime_descriptors()
_RUNTIME_ADAPTERS = {descriptor.runtime_name: get_adapter(descriptor.runtime_name) for descriptor in _RUNTIME_DESCRIPTORS}
_RUNTIME_NAMES = tuple(descriptor.runtime_name for descriptor in _RUNTIME_DESCRIPTORS)
_RUNTIME_INSTALL_FLAGS = tuple(descriptor.install_flag for descriptor in _RUNTIME_DESCRIPTORS)
_RUNTIME_DISPLAY_NAMES = {name: adapter.display_name for name, adapter in _RUNTIME_ADAPTERS.items()}
_RUNTIME_LAUNCH_COMMANDS = {name: adapter.launch_command for name, adapter in _RUNTIME_ADAPTERS.items()}
_RUNTIME_CONFIG_DIR_NAMES = {name: adapter.config_dir_name for name, adapter in _RUNTIME_ADAPTERS.items()}
_RUNTIME_HELP_COMMANDS = {name: adapter.help_command for name, adapter in _RUNTIME_ADAPTERS.items()}
_RUNTIME_NEW_PROJECT_COMMANDS = {name: adapter.new_project_command for name, adapter in _RUNTIME_ADAPTERS.items()}
_RUNTIME_MAP_RESEARCH_COMMANDS = {name: adapter.map_research_command for name, adapter in _RUNTIME_ADAPTERS.items()}
_RUNTIME_RESUME_WORK_COMMANDS = {name: adapter.format_command("resume-work") for name, adapter in _RUNTIME_ADAPTERS.items()}
_CODEX_RUNTIME_NAME = next(descriptor.runtime_name for descriptor in _RUNTIME_DESCRIPTORS if "skills/" in descriptor.manifest_file_prefixes)
_CLAUDE_RUNTIME_NAME = next(descriptor.runtime_name for descriptor in _RUNTIME_DESCRIPTORS if descriptor.launch_command == "claude")
_OPENCODE_RUNTIME_NAME = next(descriptor.runtime_name for descriptor in _RUNTIME_DESCRIPTORS if descriptor.launch_command == "opencode")
_CODEX_INSTALL_FLAG = _RUNTIME_ADAPTERS[_CODEX_RUNTIME_NAME].install_flag
_CLAUDE_INSTALL_FLAG = _RUNTIME_ADAPTERS[_CLAUDE_RUNTIME_NAME].install_flag
_CLAUDE_RUNTIME_ALIAS = _RUNTIME_ADAPTERS[_CLAUDE_RUNTIME_NAME].display_name.lower()
_OPENCODE_RUNTIME_ALIAS = next(
    alias for alias in _RUNTIME_ADAPTERS[_OPENCODE_RUNTIME_NAME].selection_aliases if " " in alias
)


def _assert_single_runtime_next_steps(output: str, runtime: str) -> None:
    pattern = re.compile(
        rf"Next steps.*?"
        rf"Open .*?{re.escape(_RUNTIME_DISPLAY_NAMES[runtime])}.*?{re.escape(_RUNTIME_LAUNCH_COMMANDS[runtime])}.*?"
        rf"Run {re.escape(_RUNTIME_HELP_COMMANDS[runtime])} for the command list\..*?"
        rf"Start with {re.escape(_RUNTIME_NEW_PROJECT_COMMANDS[runtime])} for a new project or "
        rf"{re.escape(_RUNTIME_MAP_RESEARCH_COMMANDS[runtime])} for existing work, or "
        rf"{re.escape(_RUNTIME_RESUME_WORK_COMMANDS[runtime])} to continue paused work\..*?"
        rf"Fast bootstrap: use {re.escape(_RUNTIME_NEW_PROJECT_COMMANDS[runtime])} --minimal.*?"
        rf"Use gpd --help for local install, readiness, validation, permissions, observability, and diagnostics\..*?"
        rf"Use {re.escape(_RUNTIME_HELP_COMMANDS[runtime])} inside {re.escape(_RUNTIME_DISPLAY_NAMES[runtime])} for workflow help\..*?"
        rf"Verify or troubleshoot this machine with gpd doctor --runtime {re.escape(runtime)} --(?:local|global)\..*?"
        rf"After startup, use the runtime `settings` command to review autonomy, workflow defaults, and model-cost posture\. "
        rf"The safest starting point is `review` plus runtime defaults\..*?"
        rf"If you plan to use paper/manuscript workflows, rerun gpd doctor --runtime {re.escape(runtime)} --(?:local|global) "
        rf"and check the `Optional Workflow Add-ons` and `LaTeX Toolchain` rows before publication work\.",
        re.S,
    )
    assert pattern.search(output), output


def _assert_multi_runtime_next_steps_line(output: str, runtime: str) -> None:
    pattern = re.compile(
        rf"- {re.escape(_RUNTIME_DISPLAY_NAMES[runtime])}.*?"
        rf"{re.escape(_RUNTIME_LAUNCH_COMMANDS[runtime])}.*?"
        rf"{re.escape(_RUNTIME_HELP_COMMANDS[runtime])}.*?"
        rf"{re.escape(_RUNTIME_NEW_PROJECT_COMMANDS[runtime])}.*?"
        rf"{re.escape(_RUNTIME_MAP_RESEARCH_COMMANDS[runtime])}.*?"
        rf"{re.escape(_RUNTIME_NEW_PROJECT_COMMANDS[runtime])} --minimal",
        )
    assert pattern.search(output), output


def test_version_consistency():
    """Release metadata and the bootstrap's Python pin must match."""
    assert PACKAGE_VERSION == PYTHON_PACKAGE_VERSION == str(PYPROJECT["project"]["version"])


def _write_fake_launcher(script_path: Path, command_name: str) -> None:
    script = f"""#!{sys.executable}
import sys

if sys.argv[1:] == ["--version"]:
    print({command_name!r} + " 1.0.0")

raise SystemExit(0)
"""
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(script, encoding="utf-8")
    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _write_fake_python(script_path: Path, log_path: Path, version_text: str = "Python 3.13.2") -> None:
    script = f"""#!{sys.executable}
import json
import os
import pathlib
import shutil
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
RUNTIME_LABELS = {_RUNTIME_DISPLAY_NAMES!r}
LAUNCH_COMMANDS = {_RUNTIME_LAUNCH_COMMANDS!r}
CONFIG_DIR_NAMES = {_RUNTIME_CONFIG_DIR_NAMES!r}
HELP_COMMANDS = {_RUNTIME_HELP_COMMANDS!r}
NEW_PROJECT_COMMANDS = {_RUNTIME_NEW_PROJECT_COMMANDS!r}
MAP_RESEARCH_COMMANDS = {_RUNTIME_MAP_RESEARCH_COMMANDS!r}
RESUME_WORK_COMMANDS = {_RUNTIME_RESUME_WORK_COMMANDS!r}
ALL_RUNTIMES = {_RUNTIME_NAMES!r}


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
    runtimes = [arg for arg in argv if arg in RUNTIME_LABELS]
    runtime_override = option_value(argv, "--runtime")
    if runtime_override and runtime_override in RUNTIME_LABELS:
        runtimes.append(runtime_override)
    return list(dict.fromkeys(runtimes))


def selected_scope(argv: list[str]) -> str:
    return "global" if "--global" in argv else "local"


def option_value(argv: list[str], flag: str) -> str | None:
    try:
        index = argv.index(flag)
    except ValueError:
        return None
    if index + 1 >= len(argv):
        return None
    return argv[index + 1]


def nearest_existing_ancestor(path: pathlib.Path) -> pathlib.Path:
    candidate = path.expanduser().resolve()
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def doctor_target(runtime: str, scope: str, explicit_target: str | None) -> pathlib.Path:
    if explicit_target:
        return pathlib.Path(explicit_target).expanduser().resolve()
    if scope == "global":
        return pathlib.Path(os.path.expanduser("~")).resolve() / CONFIG_DIR_NAMES[runtime]
    return pathlib.Path.cwd().resolve() / CONFIG_DIR_NAMES[runtime]


def doctor_check_runtime_launcher(runtime: str) -> dict[str, object]:
    launch_command = LAUNCH_COMMANDS[runtime]
    launch_executable = launch_command.split()[0] if launch_command.split() else launch_command
    launcher_path = shutil.which(launch_executable) if launch_executable else None
    issues = [] if launcher_path else [f"{{launch_executable or launch_command}} not found on PATH"]
    warnings = [] if launcher_path else [f"Install or expose {{RUNTIME_LABELS[runtime]}} before running GPD there."]
    return {{
        "status": "ok" if launcher_path else "fail",
        "label": "Runtime Launcher",
        "details": {{
            "runtime": runtime,
            "display_name": RUNTIME_LABELS[runtime],
            "launch_command": launch_command,
            "launch_executable": launch_executable or None,
            "launcher_path": launcher_path,
        }},
        "issues": issues,
        "warnings": warnings,
    }}


def doctor_check_runtime_target(target: pathlib.Path) -> dict[str, object]:
    resolved = target.expanduser().resolve()
    details: dict[str, object] = {{
        "target": str(resolved),
        "exists": resolved.exists(),
    }}
    issues: list[str] = []
    warnings: list[str] = []

    if resolved.exists() and not resolved.is_dir():
        issues.append(f"{{resolved}} exists but is not a directory")
        details["probe_dir"] = str(resolved)
        return {{
            "status": "fail",
            "label": "Runtime Config Target",
            "details": details,
            "issues": issues,
            "warnings": warnings,
        }}

    probe_dir = resolved if resolved.exists() else nearest_existing_ancestor(resolved.parent)
    details["probe_dir"] = str(probe_dir)
    if not probe_dir.exists():
        issues.append(f"No existing parent directory found for {{resolved}}")
    elif not probe_dir.is_dir():
        issues.append(f"{{probe_dir}} is not a directory")
    elif not os.access(probe_dir, os.W_OK | os.X_OK):
        issues.append(f"{{probe_dir}} is not writable")
    elif not resolved.exists():
        warnings.append(f"{{resolved}} does not exist yet; GPD will create it during install.")

    return {{
        "status": "fail" if issues else "ok",
        "label": "Runtime Config Target",
        "details": details,
        "issues": issues,
        "warnings": warnings,
    }}


def doctor_check_provider_auth(runtime: str, target: pathlib.Path) -> dict[str, object]:
    launch_command = LAUNCH_COMMANDS[runtime]
    return {{
        "status": "ok",
        "label": "Provider/Auth Guidance",
        "details": {{
            "runtime": runtime,
            "launch_command": launch_command,
            "target": str(target.expanduser().resolve()),
            "verification": "manual",
        }},
        "issues": [],
        "warnings": [
            (
                f"GPD does not verify provider credentials automatically for {{runtime}}. "
                f"Launch `{{launch_command}}` once and confirm your account or API provider is configured."
            )
        ],
    }}


def doctor_report(argv: list[str]) -> dict[str, object]:
    runtime = option_value(argv, "--runtime")
    scope = selected_scope(argv)
    target = doctor_target(runtime, scope, option_value(argv, "--target-dir"))
    checks = [
        {{
            "status": "ok",
            "label": "Python Runtime",
            "details": {{
                "version": {version_text!r}.replace("Python ", ""),
                "venv_available": True,
                "active_virtualenv": "venv" in pathlib.Path(sys.argv[0]).parts,
                "python_executable": sys.executable,
            }},
            "issues": [],
            "warnings": [],
        }},
        {{
            "status": "ok",
            "label": "Package Imports",
            "details": {{"modules_checked": 4}},
            "issues": [],
            "warnings": [],
        }},
        doctor_check_runtime_launcher(runtime),
        doctor_check_runtime_target(target),
        {{
            "status": "ok",
            "label": "Bootstrap Network Access",
            "details": {{"skipped": True, "reason": "disabled by GPD_BOOTSTRAP_DISABLE_NETWORK_PROBES"}},
            "issues": [],
            "warnings": [],
        }},
        doctor_check_provider_auth(runtime, target),
    ]
    ok_count = sum(1 for check in checks if check["status"] == "ok")
    warn_count = sum(1 for check in checks if check["status"] == "warn")
    fail_count = sum(1 for check in checks if check["status"] == "fail")
    overall = "fail" if fail_count > 0 else "warn" if warn_count > 0 else "ok"
    return {{
        "overall": overall,
        "version": {PYTHON_PACKAGE_VERSION!r},
        "mode": "runtime-readiness",
        "runtime": runtime,
        "install_scope": scope,
        "target": str(target),
        "summary": {{
            "ok": ok_count,
            "warn": warn_count,
            "fail": fail_count,
            "total": len(checks),
        }},
        "checks": checks,
    }}


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

if args[:4] == ["-m", "gpd.cli", "--raw", "doctor"]:
    print(json.dumps(doctor_report(args)))
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
            f"{{MAP_RESEARCH_COMMANDS[runtime]}} for existing work, or "
            f"{{RESUME_WORK_COMMANDS[runtime]}} to continue paused work."
        )
        print("")
        print(
            "   Fast bootstrap: use "
            f"{{NEW_PROJECT_COMMANDS[runtime]}} --minimal for the shortest onboarding path."
        )
        print(
            f"4. Use gpd --help for local install, readiness, validation, permissions, observability, and diagnostics. "
            f"Use {{HELP_COMMANDS[runtime]}} inside {{RUNTIME_LABELS[runtime]}} for workflow help."
        )
        print(f"5. Verify or troubleshoot this machine with gpd doctor --runtime {{runtime}} --{{scope}}.")
        print(
            "6. After startup, use the runtime `settings` command to review autonomy, workflow defaults, and model-cost posture. "
            "The safest starting point is `review` plus runtime defaults."
        )
        print(
            "7. If you plan to use paper/manuscript workflows, rerun "
            f"gpd doctor --runtime {{runtime}} --{{scope}} "
            "and check the `Optional Workflow Add-ons` and `LaTeX Toolchain` rows before publication work."
        )
    else:
        for runtime in runtimes:
            print(
                f"- {{RUNTIME_LABELS[runtime]}} ({{LAUNCH_COMMANDS[runtime]}}), then "
                f"{{HELP_COMMANDS[runtime]}}, then "
                f"{{NEW_PROJECT_COMMANDS[runtime]}} or {{MAP_RESEARCH_COMMANDS[runtime]}}. "
                f"Quick bootstrap: {{NEW_PROJECT_COMMANDS[runtime]}} --minimal"
            )
        print("Use gpd --help for local install, readiness, validation, permissions, observability, and diagnostics.")
        print("Run gpd doctor --runtime <runtime> --local|--global for a focused readiness check.")
        print(
            "After startup, use the runtime `settings` command to review autonomy, workflow defaults, and model-cost posture. "
            "The safest starting point is `review` plus runtime defaults."
        )
        print(
            "For paper/manuscript workflows, rerun gpd doctor --runtime <runtime> --local|--global "
            "and check the `Optional Workflow Add-ons` and `LaTeX Toolchain` rows before publication work."
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
    node_path = shutil.which("node")
    if node_path is None:
        raise RuntimeError("node is required for bootstrap installer tests")

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

    missing_launchers = {
        token.strip().lower()
        for token in (extra_env or {}).get("FAKE_MISSING_LAUNCHERS", "").split(",")
        if token.strip()
    }
    for runtime in _RUNTIME_NAMES:
        launch_command = _RUNTIME_LAUNCH_COMMANDS[runtime]
        if runtime.lower() in missing_launchers or launch_command.lower() in missing_launchers:
            continue
        _write_fake_launcher(fake_bin / launch_command, launch_command)

    if precreate_managed_version is not None:
        managed_bin = home / "GPD" / "venv" / "bin"
        for name in ("python", "python3"):
            _write_fake_python(managed_bin / name, log_path, precreate_managed_version)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["GPD_HOME"] = str(home / "GPD")
    env["GPD_BOOTSTRAP_DISABLE_NETWORK_PROBES"] = "1"
    env["PATH"] = os.pathsep.join([str(local_bin), str(fake_bin)])
    if extra_env:
        env.update(extra_env)

    result = subprocess.run(
        [node_path, "bin/install.js", *(installer_args or [_CODEX_INSTALL_FLAG, "--local"])],
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
        entry["argv"][:2] == ["-m", "venv"] and entry["argv"][-1].replace("\\", "/").endswith("/GPD/venv")
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
        entry for entry in entries if entry["managed"] and entry["argv"] == ["-m", "gpd.cli", "install", _CODEX_RUNTIME_NAME, "--local"]
    ]
    assert len(managed_runtime_installs) == 1
    managed_runtime_doctor = [
        entry
        for entry in entries
        if entry["managed"] and entry["argv"] == ["-m", "gpd.cli", "--raw", "doctor", "--runtime", _CODEX_RUNTIME_NAME, "--local"]
    ]
    assert len(managed_runtime_doctor) == 1
    doctor_index = next(
        index
        for index, entry in enumerate(entries)
        if entry["managed"] and entry["argv"] == ["-m", "gpd.cli", "--raw", "doctor", "--runtime", _CODEX_RUNTIME_NAME, "--local"]
    )
    install_index = next(
        index
        for index, entry in enumerate(entries)
        if entry["managed"] and entry["argv"] == ["-m", "gpd.cli", "install", _CODEX_RUNTIME_NAME, "--local"]
    )
    assert doctor_index < install_index

    assert (home / "GPD" / "venv" / "bin" / "python").exists()
    assert f"GPD v{PACKAGE_VERSION} - Get Physics Done" in result.stdout
    assert "© 2026 Physical Superintelligence PBC (PSI)" in result.stdout
    assert f"Installing GPD (local) for: {_RUNTIME_DISPLAY_NAMES[_CODEX_RUNTIME_NAME]}" in result.stdout
    assert "Runtime launcher/target preflight" in result.stdout
    assert f"{_RUNTIME_DISPLAY_NAMES[_CODEX_RUNTIME_NAME]}: launcher/target preflight passed" in result.stdout
    assert "GPD does not verify provider credentials automatically" in result.stdout
    assert f"`gpd doctor --runtime {_CODEX_RUNTIME_NAME} --local`" in result.stdout
    assert (
        "Optional workflow add-ons: if you plan paper/manuscript workflows, rerun "
        f"`gpd doctor --runtime {_CODEX_RUNTIME_NAME} --local` after install and check whether "
        "`Optional Workflow Add-ons` is `ready` or `degraded`. Without LaTeX, `write-paper` and "
        "`peer-review` remain usable, but `paper-build` and `arxiv-submission` require the `LaTeX Toolchain`."
    ) in result.stdout
    assert "Install Summary" in result.stdout
    _assert_single_runtime_next_steps(result.stdout, _CODEX_RUNTIME_NAME)
    assert "Recommended unattended default: Balanced autonomy (`balanced`)." in result.stdout
    assert "The safest model starting point is `review` plus runtime defaults." in result.stdout
    assert f"Installing GPD for {_RUNTIME_DISPLAY_NAMES[_CODEX_RUNTIME_NAME]} (local)..." not in result.stdout
    assert f"Installed GPD for {_RUNTIME_DISPLAY_NAMES[_CODEX_RUNTIME_NAME]} (local)." not in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_uninstall_routes_to_runtime_uninstall(tmp_path: Path) -> None:
    result, home, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=["--uninstall", _CODEX_INSTALL_FLAG, "--local"],
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]

    assert any(entry["argv"] == ["-m", "venv", "--help"] for entry in entries)
    assert any(
        entry["argv"][:2] == ["-m", "venv"] and entry["argv"][-1].replace("\\", "/").endswith("/GPD/venv")
        for entry in entries
    )

    managed_pip_installs = [
        entry for entry in entries if entry["managed"] and entry["argv"][:4] == ["-m", "pip", "install", "--upgrade"]
    ]
    assert len(managed_pip_installs) == 1
    assert managed_pip_installs[0]["argv"][-1] == PYPI_SPEC

    managed_runtime_uninstalls = [
        entry for entry in entries if entry["managed"] and entry["argv"] == ["-m", "gpd.cli", "uninstall", _CODEX_RUNTIME_NAME, "--local"]
    ]
    assert len(managed_runtime_uninstalls) == 1
    managed_runtime_doctor = [
        entry for entry in entries if entry["managed"] and entry["argv"][:4] == ["-m", "gpd.cli", "--raw", "doctor"]
    ]
    assert managed_runtime_doctor == []

    assert (home / "GPD" / "venv" / "bin" / "python").exists()
    assert f"Preparing managed GPD CLI from PyPI (get-physics-done=={PYTHON_PACKAGE_VERSION}) into the managed environment..." in result.stdout
    assert "Runtime launcher/target preflight" not in result.stdout
    assert f"Uninstalling GPD from {_RUNTIME_DISPLAY_NAMES[_CODEX_RUNTIME_NAME]} (local)..." in result.stdout
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
    for runtime in _RUNTIME_NAMES:
        assert _RUNTIME_DISPLAY_NAMES[runtime] in result.stdout
    assert "runtime uninstall ok" in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_install_subcommand_accepts_positional_runtime_alias(tmp_path: Path) -> None:
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=["install", _CLAUDE_RUNTIME_ALIAS, "--local"],
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    managed_runtime_installs = [
        entry for entry in entries if entry["managed"] and entry["argv"] == ["-m", "gpd.cli", "install", _CLAUDE_RUNTIME_NAME, "--local"]
    ]

    assert len(managed_runtime_installs) == 1
    assert f"Installing GPD (local) for: {_RUNTIME_DISPLAY_NAMES[_CLAUDE_RUNTIME_NAME]}" in result.stdout
    assert "Install Summary" in result.stdout
    _assert_single_runtime_next_steps(result.stdout, _CLAUDE_RUNTIME_NAME)
    assert f"Installed GPD for {_RUNTIME_DISPLAY_NAMES[_CLAUDE_RUNTIME_NAME]} (local)." not in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_uninstall_subcommand_accepts_runtime_alias(tmp_path: Path) -> None:
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=["uninstall", _OPENCODE_RUNTIME_ALIAS, "--local"],
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    managed_runtime_uninstalls = [
        entry for entry in entries if entry["managed"] and entry["argv"] == ["-m", "gpd.cli", "uninstall", _OPENCODE_RUNTIME_NAME, "--local"]
    ]

    assert len(managed_runtime_uninstalls) == 1
    assert f"Uninstalling GPD from {_RUNTIME_DISPLAY_NAMES[_OPENCODE_RUNTIME_NAME]} (local)..." in result.stdout
    assert "runtime uninstall ok" in result.stdout


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
    for runtime in _RUNTIME_NAMES:
        assert _RUNTIME_DISPLAY_NAMES[runtime] in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_install_requires_explicit_runtime_non_interactively(tmp_path: Path) -> None:
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=["--local"],
    )

    assert result.returncode == 1
    assert "Specify a runtime with" in result.stderr
    assert "when running non-interactively." in result.stderr
    for flag in _RUNTIME_INSTALL_FLAGS:
        assert flag in result.stderr
    assert not log_path.exists()


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_install_requires_explicit_scope_non_interactively(tmp_path: Path) -> None:
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=[_CODEX_INSTALL_FLAG],
    )

    assert result.returncode == 1
    assert "Specify --global or --local when running non-interactively." in result.stderr
    assert not log_path.exists()


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_install_blocks_when_selected_runtime_launcher_is_missing(tmp_path: Path) -> None:
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        extra_env={"FAKE_MISSING_LAUNCHERS": _CODEX_RUNTIME_NAME},
    )

    assert result.returncode == 1

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    managed_pip_installs = [
        entry for entry in entries if entry["managed"] and entry["argv"][:4] == ["-m", "pip", "install", "--upgrade"]
    ]
    assert len(managed_pip_installs) == 1

    managed_runtime_doctor = [
        entry
        for entry in entries
        if entry["managed"] and entry["argv"] == ["-m", "gpd.cli", "--raw", "doctor", "--runtime", _CODEX_RUNTIME_NAME, "--local"]
    ]
    assert len(managed_runtime_doctor) == 1
    managed_runtime_installs = [
        entry for entry in entries if entry["managed"] and entry["argv"][:3] == ["-m", "gpd.cli", "install"]
    ]
    assert managed_runtime_installs == []
    assert "Runtime launcher/target preflight failed." in result.stderr
    assert (
        f"{_RUNTIME_DISPLAY_NAMES[_CODEX_RUNTIME_NAME]}: Runtime Launcher: "
        f"{_RUNTIME_LAUNCH_COMMANDS[_CODEX_RUNTIME_NAME]} not found on PATH"
    ) in result.stderr
    assert f"`gpd doctor --runtime {_CODEX_RUNTIME_NAME} --local`" in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_install_blocks_when_target_dir_is_not_writable(tmp_path: Path) -> None:
    protected_parent = tmp_path / "protected"
    protected_parent.mkdir()
    protected_parent.chmod(0o555)
    target_dir = protected_parent / _RUNTIME_ADAPTERS[_CODEX_RUNTIME_NAME].config_dir_name

    try:
        result, _, log_path = _run_bootstrap_with_fake_python(
            tmp_path,
            installer_args=[_CODEX_INSTALL_FLAG, "--local", "--target-dir", str(target_dir)],
        )
    finally:
        protected_parent.chmod(0o755)

    assert result.returncode == 1

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    managed_pip_installs = [
        entry for entry in entries if entry["managed"] and entry["argv"][:4] == ["-m", "pip", "install", "--upgrade"]
    ]
    assert len(managed_pip_installs) == 1

    managed_runtime_doctor = [
        entry
        for entry in entries
        if entry["managed"]
        and entry["argv"] == [
            "-m",
            "gpd.cli",
            "--raw",
            "doctor",
            "--runtime",
            _CODEX_RUNTIME_NAME,
            "--local",
            "--target-dir",
            str(target_dir),
        ]
    ]
    assert len(managed_runtime_doctor) == 1
    managed_runtime_installs = [
        entry for entry in entries if entry["managed"] and entry["argv"][:3] == ["-m", "gpd.cli", "install"]
    ]
    assert managed_runtime_installs == []
    assert "Runtime launcher/target preflight failed." in result.stderr
    assert f"{_RUNTIME_DISPLAY_NAMES[_CODEX_RUNTIME_NAME]}: Runtime Config Target:" in result.stderr
    assert "is not writable" in result.stderr
    assert f"`gpd doctor --runtime {_CODEX_RUNTIME_NAME} --local --target-dir {target_dir}`" in result.stdout


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
    for flag in _RUNTIME_INSTALL_FLAGS:
        assert flag in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_uninstall_requires_explicit_scope_non_interactively(tmp_path: Path) -> None:
    result, _, _ = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=["--uninstall", _CODEX_INSTALL_FLAG],
    )

    assert result.returncode == 1
    assert "Specify --global or --local when running --uninstall non-interactively." in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_uninstall_rejects_reinstall_flag(tmp_path: Path) -> None:
    result, _, _ = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=["--uninstall", _CODEX_INSTALL_FLAG, "--local", "--reinstall"],
    )

    assert result.returncode == 1
    assert "Cannot combine --uninstall with --reinstall." in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_rejects_reinstall_and_upgrade_together(tmp_path: Path) -> None:
    result, _, _ = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=[_CODEX_INSTALL_FLAG, "--local", "--reinstall", "--upgrade"],
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
    assert f"Installed GPD for {_RUNTIME_DISPLAY_NAMES[_CODEX_RUNTIME_NAME]} (local)." not in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_forwards_target_dir_to_runtime_install(tmp_path: Path) -> None:
    target_dir = tmp_path / "custom target" / _RUNTIME_ADAPTERS[_CODEX_RUNTIME_NAME].config_dir_name
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=[_CODEX_INSTALL_FLAG, "--target-dir", str(target_dir)],
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    managed_runtime_installs = [
        entry
        for entry in entries
        if entry["managed"]
        and entry["argv"] == ["-m", "gpd.cli", "install", _CODEX_RUNTIME_NAME, "--local", "--target-dir", str(target_dir)]
    ]
    assert len(managed_runtime_installs) == 1
    managed_runtime_doctor = [
        entry
        for entry in entries
        if entry["managed"]
        and entry["argv"] == [
            "-m",
            "gpd.cli",
            "--raw",
            "doctor",
            "--runtime",
            _CODEX_RUNTIME_NAME,
            "--local",
            "--target-dir",
            str(target_dir),
        ]
    ]
    assert len(managed_runtime_doctor) == 1


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_preserves_global_scope_for_canonical_global_target_dir(tmp_path: Path) -> None:
    home = tmp_path / "home"
    target_dir = home / _RUNTIME_ADAPTERS[_CODEX_RUNTIME_NAME].config_dir_name
    result, _home, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=[_CODEX_INSTALL_FLAG, "--target-dir", str(target_dir)],
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    managed_runtime_installs = [
        entry
        for entry in entries
        if entry["managed"]
        and entry["argv"] == ["-m", "gpd.cli", "install", _CODEX_RUNTIME_NAME, "--global", "--target-dir", str(target_dir)]
    ]

    assert len(managed_runtime_installs) == 1
    managed_runtime_doctor = [
        entry
        for entry in entries
        if entry["managed"]
        and entry["argv"] == [
            "-m",
            "gpd.cli",
            "--raw",
            "doctor",
            "--runtime",
            _CODEX_RUNTIME_NAME,
            "--global",
            "--target-dir",
            str(target_dir),
        ]
    ]
    assert len(managed_runtime_doctor) == 1
    assert f"Installing GPD (global) for: {_RUNTIME_DISPLAY_NAMES[_CODEX_RUNTIME_NAME]}" in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_requires_explicit_runtime_with_target_dir_non_interactively(tmp_path: Path) -> None:
    target_dir = tmp_path / "custom target"
    result, _, log_path = _run_bootstrap_with_fake_python(
        tmp_path,
        installer_args=["--target-dir", str(target_dir)],
    )

    assert result.returncode == 1
    assert "Specify exactly one runtime with" in result.stderr
    assert "when using --target-dir non-interactively." in result.stderr
    for flag in _RUNTIME_INSTALL_FLAGS:
        assert flag in result.stderr
    assert not log_path.exists()


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
        installer_args=[_CODEX_INSTALL_FLAG, "--local", "--reinstall"],
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
        installer_args=[_CLAUDE_INSTALL_FLAG, "--local", "--upgrade"],
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
        installer_args=[_CLAUDE_INSTALL_FLAG, "--local", "--upgrade"],
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
        installer_args=[_CLAUDE_INSTALL_FLAG, "--local", "--upgrade"],
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
        installer_args=[_CLAUDE_INSTALL_FLAG, "--local", "--upgrade"],
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
    for runtime in _RUNTIME_NAMES:
        assert _RUNTIME_DISPLAY_NAMES[runtime] in result.stdout
    assert "Install Summary" in result.stdout
    assert "Next steps" in result.stdout
    assert (
        "Optional workflow add-ons: if you plan paper/manuscript workflows, rerun "
        + ", ".join(f"`gpd doctor --runtime {runtime} --global`" for runtime in _RUNTIME_NAMES)
        + " after install and check whether `Optional Workflow Add-ons` is `ready` or `degraded`. "
        + "Without LaTeX, `write-paper` and `peer-review` remain usable, but `paper-build` and "
        + "`arxiv-submission` require the `LaTeX Toolchain`."
    ) in result.stdout
    for runtime in _RUNTIME_NAMES:
        _assert_multi_runtime_next_steps_line(result.stdout, runtime)
    assert "Use gpd --help for local install, readiness, validation, permissions, observability, and diagnostics." in result.stdout


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
    assert (home / "GPD" / "venv" / "bin" / "python").exists()
