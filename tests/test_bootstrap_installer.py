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

import gpd.adapters.runtime_catalog as runtime_catalog_module
import gpd.core.public_surface_contract as public_surface_contract_module
from gpd.adapters import get_adapter, iter_runtime_descriptors
from gpd.core.public_surface_contract import beginner_onboarding_hub_url
from gpd.core.surface_phrases import recovery_ladder_note
from tests.doc_surface_contracts import (
    assert_install_summary_runtime_follow_up_contract,
    assert_recovery_ladder_contract,
)
from tests.runtime_test_support import PRIMARY_RUNTIME, runtime_install_flag, runtime_with_multiword_alias

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
_RUNTIME_START_COMMANDS = {name: adapter.format_command("start") for name, adapter in _RUNTIME_ADAPTERS.items()}
_RUNTIME_TOUR_COMMANDS = {name: adapter.format_command("tour") for name, adapter in _RUNTIME_ADAPTERS.items()}
_RUNTIME_NEW_PROJECT_COMMANDS = {name: adapter.new_project_command for name, adapter in _RUNTIME_ADAPTERS.items()}
_RUNTIME_MAP_RESEARCH_COMMANDS = {name: adapter.map_research_command for name, adapter in _RUNTIME_ADAPTERS.items()}
_RUNTIME_RESUME_WORK_COMMANDS = {name: adapter.format_command("resume-work") for name, adapter in _RUNTIME_ADAPTERS.items()}
_RUNTIME_SUGGEST_NEXT_COMMANDS = {name: adapter.format_command("suggest-next") for name, adapter in _RUNTIME_ADAPTERS.items()}
_RUNTIME_PAUSE_WORK_COMMANDS = {name: adapter.format_command("pause-work") for name, adapter in _RUNTIME_ADAPTERS.items()}
_RUNTIME_HELP_EXAMPLE_DESCRIPTORS = tuple(
    descriptor for descriptor in _RUNTIME_DESCRIPTORS if descriptor.installer_help_example_scope is not None
)
_CODEX_RUNTIME_NAME = PRIMARY_RUNTIME
_CLAUDE_RUNTIME_NAME, _CLAUDE_RUNTIME_ALIAS = runtime_with_multiword_alias(exclude=(_CODEX_RUNTIME_NAME,))
_OPENCODE_RUNTIME_NAME, _OPENCODE_RUNTIME_ALIAS = runtime_with_multiword_alias(
    exclude=(_CODEX_RUNTIME_NAME, _CLAUDE_RUNTIME_NAME)
)
_BEGINNER_ONBOARDING_HUB_URL = beginner_onboarding_hub_url()
_LOCAL_CLI_BRIDGE_NOTE = public_surface_contract_module.local_cli_bridge_note()
_CODEX_INSTALL_FLAG = runtime_install_flag(_CODEX_RUNTIME_NAME)
_CLAUDE_INSTALL_FLAG = runtime_install_flag(_CLAUDE_RUNTIME_NAME)
_GENERIC_RECOVERY_LADDER_NOTE = recovery_ladder_note(
    resume_work_phrase="your runtime-specific `resume-work` command",
    suggest_next_phrase="your runtime-specific `suggest-next` command",
    pause_work_phrase="your runtime-specific `pause-work` command",
)
_RUNTIME_RECOVERY_LADDER_TEMPLATE = recovery_ladder_note(
    resume_work_phrase="{resume_work}",
    suggest_next_phrase="{suggest_next}",
    pause_work_phrase="{pause_work}",
)


def _render_runtime_recovery_ladder(runtime: str) -> str:
    return _RUNTIME_RECOVERY_LADDER_TEMPLATE.format(
        resume_work=f"`{_RUNTIME_RESUME_WORK_COMMANDS[runtime]}`",
        suggest_next=f"`{_RUNTIME_SUGGEST_NEXT_COMMANDS[runtime]}`",
        pause_work=f"`{_RUNTIME_PAUSE_WORK_COMMANDS[runtime]}`",
    )


def _assert_single_runtime_next_steps(output: str, runtime: str) -> None:
    resume_work_command = _RUNTIME_RESUME_WORK_COMMANDS[runtime]
    suggest_next_command = _RUNTIME_SUGGEST_NEXT_COMMANDS[runtime]
    pause_work_command = _RUNTIME_PAUSE_WORK_COMMANDS[runtime]
    ordered_patterns = (
        re.escape("Startup checklist"),
        re.escape(f"Beginner Onboarding Hub: {_BEGINNER_ONBOARDING_HUB_URL}"),
        re.escape("First-run order: `help -> start -> tour -> new-project / map-research -> resume-work`"),
        re.escape(
            f"1. Open {_RUNTIME_DISPLAY_NAMES[runtime]} from your system terminal ({_RUNTIME_LAUNCH_COMMANDS[runtime]})."
        ),
        re.escape(f"2. Run {_RUNTIME_HELP_COMMANDS[runtime]} for the command list."),
        re.escape(
            "3. Run "
            f"{_RUNTIME_START_COMMANDS[runtime]} if you're not sure what fits this folder yet. "
            "Run "
            f"{_RUNTIME_TOUR_COMMANDS[runtime]} if you want a read-only overview of the broader command surface first."
        ),
        re.escape(
            "4. Then use "
            f"{_RUNTIME_NEW_PROJECT_COMMANDS[runtime]} for a new project or "
            f"{_RUNTIME_MAP_RESEARCH_COMMANDS[runtime]} for existing work."
        ),
        re.escape(
            f"5. Fast bootstrap: use {_RUNTIME_NEW_PROJECT_COMMANDS[runtime]} --minimal for the shortest onboarding path."
        ),
        re.escape(
            f"6. When you return later, use {resume_work_command} after reopening the right workspace. "
        ),
        re.escape(
            recovery_ladder_note(
                resume_work_phrase=f"`{resume_work_command}`",
                suggest_next_phrase=f"`{suggest_next_command}`",
                pause_work_phrase=f"`{pause_work_command}`",
            )
        ),
        re.escape("7. Use gpd --help for local diagnostics and later setup."),
    )
    cursor = 0
    for pattern in ordered_patterns:
        match = re.search(pattern, output[cursor:], re.S)
        assert match, output
        cursor += match.end()

    _assert_install_summary_semantic_contract(
        output,
        runtime_help_fragments=(
            f"Run {_RUNTIME_HELP_COMMANDS[runtime]} for the command list.",
        ),
        resume_work_fragments=(f"`{_RUNTIME_RESUME_WORK_COMMANDS[runtime]}`",),
        suggest_next_fragments=(f"`{_RUNTIME_SUGGEST_NEXT_COMMANDS[runtime]}`",),
        pause_work_fragments=(f"`{_RUNTIME_PAUSE_WORK_COMMANDS[runtime]}`",),
    )


def _assert_multi_runtime_next_steps_line(output: str, runtime: str) -> None:
    pattern = re.compile(
        rf"- {re.escape(_RUNTIME_DISPLAY_NAMES[runtime])}.*?"
        rf"{re.escape(_RUNTIME_LAUNCH_COMMANDS[runtime])}.*?"
        rf"{re.escape(_RUNTIME_HELP_COMMANDS[runtime])}.*?"
        rf"{re.escape(_RUNTIME_START_COMMANDS[runtime])}.*?"
        rf"{re.escape(_RUNTIME_TOUR_COMMANDS[runtime])}.*?"
        rf"{re.escape(_RUNTIME_NEW_PROJECT_COMMANDS[runtime])}.*?"
        rf"{re.escape(_RUNTIME_MAP_RESEARCH_COMMANDS[runtime])}.*?"
        rf"{re.escape(_RUNTIME_RESUME_WORK_COMMANDS[runtime])}.*?"
        rf"Fast bootstrap: use .*? --minimal",
        re.S,
    )
    assert pattern.search(output), output


def _assert_install_summary_semantic_contract(
    output: str,
    *,
    runtime_help_fragments: tuple[str, ...],
    resume_work_fragments: tuple[str, ...],
    suggest_next_fragments: tuple[str, ...],
    pause_work_fragments: tuple[str, ...],
) -> None:
    assert_recovery_ladder_contract(
        output,
        resume_work_fragments=resume_work_fragments,
        suggest_next_fragments=suggest_next_fragments,
        pause_work_fragments=pause_work_fragments,
    )
    assert_install_summary_runtime_follow_up_contract(output, runtime_help_fragments=runtime_help_fragments)


def test_version_consistency():
    """Release metadata and the bootstrap's Python pin must match."""
    assert PACKAGE_VERSION == PYTHON_PACKAGE_VERSION == str(PYPROJECT["project"]["version"])


def test_runtime_recovery_ladder_template_stays_in_sync_with_shared_surface_phrase() -> None:
    for runtime in _RUNTIME_NAMES:
        ladder_note = _render_runtime_recovery_ladder(runtime)

        assert ladder_note == recovery_ladder_note(
            resume_work_phrase=f"`{_RUNTIME_RESUME_WORK_COMMANDS[runtime]}`",
            suggest_next_phrase=f"`{_RUNTIME_SUGGEST_NEXT_COMMANDS[runtime]}`",
            pause_work_phrase=f"`{_RUNTIME_PAUSE_WORK_COMMANDS[runtime]}`",
        )
        assert_recovery_ladder_contract(
            ladder_note,
            resume_work_fragments=(f"`{_RUNTIME_RESUME_WORK_COMMANDS[runtime]}`",),
            suggest_next_fragments=(f"`{_RUNTIME_SUGGEST_NEXT_COMMANDS[runtime]}`",),
            pause_work_fragments=(f"`{_RUNTIME_PAUSE_WORK_COMMANDS[runtime]}`",),
        )


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
START_COMMANDS = {_RUNTIME_START_COMMANDS!r}
TOUR_COMMANDS = {_RUNTIME_TOUR_COMMANDS!r}
NEW_PROJECT_COMMANDS = {_RUNTIME_NEW_PROJECT_COMMANDS!r}
MAP_RESEARCH_COMMANDS = {_RUNTIME_MAP_RESEARCH_COMMANDS!r}
RESUME_WORK_COMMANDS = {_RUNTIME_RESUME_WORK_COMMANDS!r}
SUGGEST_NEXT_COMMANDS = {_RUNTIME_SUGGEST_NEXT_COMMANDS!r}
PAUSE_WORK_COMMANDS = {_RUNTIME_PAUSE_WORK_COMMANDS!r}
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


def recovery_ladder_for_runtime(runtime: str) -> str:
    return {_RUNTIME_RECOVERY_LADDER_TEMPLATE!r}.format(
        resume_work=f"`{{RESUME_WORK_COMMANDS[runtime]}}`",
        suggest_next=f"`{{SUGGEST_NEXT_COMMANDS[runtime]}}`",
        pause_work=f"`{{PAUSE_WORK_COMMANDS[runtime]}}`",
    )


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
    print("Startup checklist")
    print(f"Beginner Onboarding Hub: {_BEGINNER_ONBOARDING_HUB_URL}")
    print("First-run order: `help -> start -> tour -> new-project / map-research -> resume-work`")
    if len(runtimes) == 1:
        runtime = runtimes[0]
        print(
            f"1. Open {{RUNTIME_LABELS[runtime]}} from your system terminal "
            f"({{LAUNCH_COMMANDS[runtime]}})."
        )
        print(f"2. Run {{HELP_COMMANDS[runtime]}} for the command list.")
        print(
            "3. Run "
            f"{{START_COMMANDS[runtime]}} if you're not sure what fits this folder yet. "
            "Run "
            f"{{TOUR_COMMANDS[runtime]}} if you want a read-only overview of the broader command surface first."
        )
        print(
            "4. Then use "
            f"{{NEW_PROJECT_COMMANDS[runtime]}} for a new project or "
            f"{{MAP_RESEARCH_COMMANDS[runtime]}} for existing work."
        )
        print(
            "5. Fast bootstrap: use "
            f"{{NEW_PROJECT_COMMANDS[runtime]}} --minimal for the shortest onboarding path."
        )
        print(
            f"6. When you return later, use {{RESUME_WORK_COMMANDS[runtime]}} after reopening the right workspace. "
            f"{{recovery_ladder_for_runtime(runtime)}}"
        )
        print("7. Use gpd --help for local diagnostics and later setup.")
    else:
        for runtime in runtimes:
            print(
                f"- {{RUNTIME_LABELS[runtime]}} ({{LAUNCH_COMMANDS[runtime]}}): "
                f"{{HELP_COMMANDS[runtime]}}, then "
                f"{{START_COMMANDS[runtime]}}, then "
                f"{{TOUR_COMMANDS[runtime]}}, then "
                f"{{NEW_PROJECT_COMMANDS[runtime]}} for new work or "
                f"{{MAP_RESEARCH_COMMANDS[runtime]}} for existing work, then "
                f"{{RESUME_WORK_COMMANDS[runtime]}} when you return later."
            )
        print(
            f"Fast bootstrap: use {{NEW_PROJECT_COMMANDS[runtimes[0]]}} --minimal for the shortest onboarding path."
        )
        print({_GENERIC_RECOVERY_LADDER_NOTE!r})
        print("Use gpd --help for local diagnostics and later setup.")
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

    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("FAKE_PIP_")
    }
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


def _run_node_contract_validation(script: str) -> subprocess.CompletedProcess[str]:
    node_path = shutil.which("node")
    if node_path is None:
        raise RuntimeError("node is required for bootstrap installer tests")

    return subprocess.run(
        [node_path, "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _load_public_surface_contract_from_payload(
    payload: dict[str, object],
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    schema_payload: dict[str, object] | None = None,
):
    class _FakeFiles:
        def __init__(self, contract_path: Path, schema_path: Path) -> None:
            self._contract_path = contract_path
            self._schema_path = schema_path

        def joinpath(self, name: str) -> Path:
            if name == "public_surface_contract.json":
                return self._contract_path
            if name == "public_surface_contract_schema.json":
                return self._schema_path
            raise AssertionError(f"Unexpected public surface contract resource: {name}")

    contract_path = tmp_path / "public_surface_contract.json"
    schema_path = tmp_path / "public_surface_contract_schema.json"
    contract_path.write_text(json.dumps(payload), encoding="utf-8")
    if schema_payload is None:
        schema_payload = json.loads(
            (REPO_ROOT / "src" / "gpd" / "core" / "public_surface_contract_schema.json").read_text(encoding="utf-8")
        )
    schema_path.write_text(json.dumps(schema_payload), encoding="utf-8")
    monkeypatch.setattr(
        public_surface_contract_module,
        "files",
        lambda package: _FakeFiles(contract_path, schema_path),
    )
    public_surface_contract_module.load_public_surface_contract.cache_clear()
    try:
        return public_surface_contract_module.load_public_surface_contract()
    finally:
        public_surface_contract_module.load_public_surface_contract.cache_clear()


def _iter_runtime_descriptors_from_payload(
    payload: list[dict[str, object]],
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    catalog_path = tmp_path / "runtime_catalog.json"
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(runtime_catalog_module, "_catalog_path", lambda: catalog_path)
    runtime_catalog_module._load_catalog.cache_clear()
    try:
        return runtime_catalog_module.iter_runtime_descriptors()
    finally:
        runtime_catalog_module._load_catalog.cache_clear()


def test_bootstrap_public_surface_contract_validator_rejects_additive_keys_and_missing_required_fields() -> None:
    result = _run_node_contract_validation(
        r"""
const assert = require("node:assert/strict");
const { loadSharedPublicSurfaceText, validateSharedPublicSurfaceContract } = require("./bin/install.js");
const payload = require("./src/gpd/core/public_surface_contract.json");

assert.doesNotThrow(() => validateSharedPublicSurfaceContract(payload));
const sharedText = loadSharedPublicSurfaceText();
assert.equal(sharedText.localCliBridge.helpCommand, payload.local_cli_bridge.named_commands.help);
assert.equal(sharedText.localCliBridge.doctorCommand, payload.local_cli_bridge.named_commands.doctor);
assert.equal(sharedText.localCliBridge.unattendedReadinessCommand, payload.local_cli_bridge.named_commands.unattended_readiness);
assert.equal(sharedText.localCliBridge.permissionsStatusCommand, payload.local_cli_bridge.named_commands.permissions_status);
assert.equal(sharedText.localCliBridge.permissionsSyncCommand, payload.local_cli_bridge.named_commands.permissions_sync);
assert.equal(sharedText.localCliBridge.resumeCommand, payload.local_cli_bridge.named_commands.resume);
assert.equal(sharedText.localCliBridge.resumeRecentCommand, payload.local_cli_bridge.named_commands.resume_recent);
assert.equal(sharedText.localCliBridge.observeExecutionCommand, payload.local_cli_bridge.named_commands.observe_execution);
assert.equal(sharedText.localCliBridge.costCommand, payload.local_cli_bridge.named_commands.cost);
assert.equal(sharedText.localCliBridge.presetsListCommand, payload.local_cli_bridge.named_commands.presets_list);
assert.equal(sharedText.localCliBridge.planPreflightCommand, payload.local_cli_bridge.named_commands.plan_preflight);
assert.equal(sharedText.localCliBridge.terminalPhrase, payload.local_cli_bridge.terminal_phrase);
assert.equal(sharedText.localCliBridge.purposePhrase, payload.local_cli_bridge.purpose_phrase);
assert.match(sharedText.localCliBridge.purposePhrase, /typed command validation/);
assert.equal(sharedText.localCliBridge.installLocalExample, payload.local_cli_bridge.install_local_example);
assert.equal(sharedText.localCliBridge.doctorLocalCommand, payload.local_cli_bridge.doctor_local_command);
assert.equal(sharedText.localCliBridge.doctorGlobalCommand, payload.local_cli_bridge.doctor_global_command);
assert.equal(
  sharedText.localCliBridge.validateCommandContextCommand,
  payload.local_cli_bridge.validate_command_context_command
);
assert.equal(
  sharedText.localCliBridge.integrationsStatusWolframCommand,
  payload.local_cli_bridge.named_commands.integrations_status_wolfram
);
assert.equal(sharedText.resumeAuthority.publicVocabularyIntro, payload.resume_authority.public_vocabulary_intro);
assert.deepEqual(sharedText.resumeAuthority.publicFields, payload.resume_authority.public_fields);
assert.equal(sharedText.recoveryLadder.localSnapshotCommand, payload.recovery_ladder.local_snapshot_command);
assert.equal(sharedText.recoveryLadder.crossWorkspaceCommand, payload.recovery_ladder.cross_workspace_command);

const additivePayload = JSON.parse(JSON.stringify(payload));
additivePayload.legacy_note = "unexpected";
additivePayload.resume_authority.legacy_note = "unexpected";
assert.throws(
  () => validateSharedPublicSurfaceContract(additivePayload),
  /public surface contract contains unknown key\(s\): legacy_note/
);

for (const sectionName of [
  "beginner_onboarding",
  "local_cli_bridge",
  "post_start_settings",
  "resume_authority",
  "recovery_ladder",
]) {
  const sectionPayload = JSON.parse(JSON.stringify(payload));
  sectionPayload[sectionName].legacy_note = "unexpected";
  assert.throws(
    () => validateSharedPublicSurfaceContract(sectionPayload),
    new RegExp(`${sectionName} contains unknown key\\(s\\): legacy_note`)
  );
}

const missingRequiredPayload = JSON.parse(JSON.stringify(payload));
delete missingRequiredPayload.resume_authority.public_vocabulary_intro;
assert.throws(
  () => validateSharedPublicSurfaceContract(missingRequiredPayload),
  /resume_authority is missing required key\(s\): public_vocabulary_intro/
);

const invalidRequiredPayload = JSON.parse(JSON.stringify(payload));
invalidRequiredPayload.resume_authority.public_fields = "unexpected";
assert.throws(
  () => validateSharedPublicSurfaceContract(invalidRequiredPayload),
  /resume_authority\.public_fields must be a non-empty list/
);

const driftedRecoveryPayload = JSON.parse(JSON.stringify(payload));
driftedRecoveryPayload.recovery_ladder.local_snapshot_command = driftedRecoveryPayload.local_cli_bridge.named_commands.help;
assert.throws(
  () => validateSharedPublicSurfaceContract(driftedRecoveryPayload),
  /recovery_ladder\.local_snapshot_command must equal local_cli_bridge\.named_commands\.resume/
);

const driftedRecentRecoveryPayload = JSON.parse(JSON.stringify(payload));
driftedRecentRecoveryPayload.recovery_ladder.cross_workspace_command = driftedRecentRecoveryPayload.local_cli_bridge.named_commands.doctor;
assert.throws(
  () => validateSharedPublicSurfaceContract(driftedRecentRecoveryPayload),
  /recovery_ladder\.cross_workspace_command must equal local_cli_bridge\.named_commands\.resume_recent/
);
"""
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"


def test_bootstrap_public_surface_contract_validator_requires_authoritative_bridge_commands() -> None:
    result = _run_node_contract_validation(
        r"""
const assert = require("node:assert/strict");
const { validateSharedPublicSurfaceContract } = require("./bin/install.js");
const payload = require("./src/gpd/core/public_surface_contract.json");

const missingDoctorPayload = JSON.parse(JSON.stringify(payload));
missingDoctorPayload.local_cli_bridge.commands = missingDoctorPayload.local_cli_bridge.commands.filter(
  (command) => command !== "gpd doctor"
);
assert.throws(
  () => validateSharedPublicSurfaceContract(missingDoctorPayload),
  /local_cli_bridge\.commands must include "gpd doctor"/
);
"""
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"


def test_bootstrap_public_surface_contract_validator_normalizes_whitespace() -> None:
    result = _run_node_contract_validation(
        r"""
const assert = require("node:assert/strict");
const { validateSharedPublicSurfaceContract } = require("./bin/install.js");
const payload = require("./src/gpd/core/public_surface_contract.json");

const noisyPayload = JSON.parse(JSON.stringify(payload));
noisyPayload.beginner_onboarding.hub_url = `  ${payload.beginner_onboarding.hub_url}  `;
noisyPayload.beginner_onboarding.startup_ladder = [
  `  ${payload.beginner_onboarding.startup_ladder[0]}  `,
  ...payload.beginner_onboarding.startup_ladder.slice(1),
];
noisyPayload.local_cli_bridge.commands = [
  `  ${payload.local_cli_bridge.commands[0]}  `,
  ...payload.local_cli_bridge.commands.slice(1),
];
noisyPayload.local_cli_bridge.named_commands.doctor = `  ${payload.local_cli_bridge.named_commands.doctor}  `;
noisyPayload.post_start_settings.primary_sentence = `  ${payload.post_start_settings.primary_sentence}  `;
noisyPayload.resume_authority.public_fields = [
  payload.resume_authority.public_fields[0],
  `  ${payload.resume_authority.public_fields[1]}  `,
  ...payload.resume_authority.public_fields.slice(2),
];
noisyPayload.recovery_ladder.title = `  ${payload.recovery_ladder.title}  `;

const normalized = validateSharedPublicSurfaceContract(noisyPayload);

assert.equal(normalized.beginnerHubUrl, payload.beginner_onboarding.hub_url);
assert.deepEqual(normalized.beginnerStartupLadder, payload.beginner_onboarding.startup_ladder);
assert.deepEqual(normalized.localCliBridgeCommands, payload.local_cli_bridge.commands);
assert.equal(normalized.localCliBridge.doctorCommand, payload.local_cli_bridge.named_commands.doctor);
assert.equal(normalized.settingsCommandSentence, payload.post_start_settings.primary_sentence);
assert.deepEqual(normalized.resumeAuthority.publicFields, payload.resume_authority.public_fields);
assert.equal(normalized.recoveryLadder.title, payload.recovery_ladder.title);
"""
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"


def test_bootstrap_public_surface_contract_validator_rejects_duplicate_entries() -> None:
    result = _run_node_contract_validation(
        r"""
const assert = require("node:assert/strict");
const { validateSharedPublicSurfaceContract } = require("./bin/install.js");
const payload = require("./src/gpd/core/public_surface_contract.json");

const duplicatePayload = JSON.parse(JSON.stringify(payload));
duplicatePayload.local_cli_bridge.commands.push(payload.local_cli_bridge.commands[0]);
assert.throws(
  () => validateSharedPublicSurfaceContract(duplicatePayload),
  /local_cli_bridge\.commands must not contain duplicates/
);
"""
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"


def test_bootstrap_public_surface_contract_validator_stays_in_parity_with_python_loader(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    canonical_payload = json.loads((REPO_ROOT / "src" / "gpd" / "core" / "public_surface_contract.json").read_text(encoding="utf-8"))
    python_contract = _load_public_surface_contract_from_payload(canonical_payload, tmp_path=tmp_path, monkeypatch=monkeypatch)

    assert python_contract.beginner_onboarding.hub_url == _BEGINNER_ONBOARDING_HUB_URL
    assert python_contract.resume_authority.public_fields[0] == "active_resume_kind"

    canonical_result = _run_node_contract_validation(
        f"""
const assert = require("node:assert/strict");
const {{ validateSharedPublicSurfaceContract }} = require("./bin/install.js");
const payload = {json.dumps(canonical_payload)};
const normalized = validateSharedPublicSurfaceContract(payload);
assert.equal(normalized.beginnerHubUrl, payload.beginner_onboarding.hub_url);
assert.equal(normalized.resumeAuthority.publicVocabularyIntro, payload.resume_authority.public_vocabulary_intro);
assert.equal(normalized.recoveryLadder.localSnapshotCommand, payload.recovery_ladder.local_snapshot_command);
"""
    )
    assert canonical_result.returncode == 0, f"{canonical_result.stdout}\n{canonical_result.stderr}"

    additive_payload = json.loads((REPO_ROOT / "src" / "gpd" / "core" / "public_surface_contract.json").read_text(encoding="utf-8"))
    additive_payload["legacy_note"] = "unexpected"
    with pytest.raises(ValueError, match=r"public_surface_contract contains unknown key\(s\): legacy_note"):
        _load_public_surface_contract_from_payload(additive_payload, tmp_path=tmp_path, monkeypatch=monkeypatch)
    additive_result = _run_node_contract_validation(
        f"""
const assert = require("node:assert/strict");
const {{ validateSharedPublicSurfaceContract }} = require("./bin/install.js");
const payload = {json.dumps(additive_payload)};
assert.throws(() => validateSharedPublicSurfaceContract(payload), /public surface contract contains unknown key\\(s\\): legacy_note/);
"""
    )
    assert additive_result.returncode == 0, f"{additive_result.stdout}\n{additive_result.stderr}"

    missing_payload = json.loads((REPO_ROOT / "src" / "gpd" / "core" / "public_surface_contract.json").read_text(encoding="utf-8"))
    del missing_payload["resume_authority"]["public_vocabulary_intro"]
    with pytest.raises(ValueError, match=r"resume_authority is missing required key\(s\): public_vocabulary_intro"):
        _load_public_surface_contract_from_payload(missing_payload, tmp_path=tmp_path, monkeypatch=monkeypatch)
    missing_result = _run_node_contract_validation(
        f"""
const assert = require("node:assert/strict");
const {{ validateSharedPublicSurfaceContract }} = require("./bin/install.js");
const payload = {json.dumps(missing_payload)};
assert.throws(
  () => validateSharedPublicSurfaceContract(payload),
  /resume_authority is missing required key\\(s\\): public_vocabulary_intro/
);
"""
    )
    assert missing_result.returncode == 0, f"{missing_result.stdout}\n{missing_result.stderr}"


def test_bootstrap_public_surface_contract_schema_validator_stays_in_parity_with_python_loader(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    canonical_payload = json.loads(
        (REPO_ROOT / "src" / "gpd" / "core" / "public_surface_contract.json").read_text(encoding="utf-8")
    )
    canonical_schema = json.loads(
        (REPO_ROOT / "src" / "gpd" / "core" / "public_surface_contract_schema.json").read_text(encoding="utf-8")
    )
    drifted_payload = json.loads(json.dumps(canonical_payload))
    drifted_schema = json.loads(json.dumps(canonical_schema))
    drifted_payload["beginner_onboarding"]["legacy_note"] = "unexpected"
    drifted_schema["sections"]["beginner_onboarding"]["keys"].append("legacy_note")

    with pytest.raises(
        ValueError,
        match=(
            r"public_surface_contract_schema\.sections\.beginner_onboarding\.keys must exactly match "
            r"the code-supported contract fields"
        ),
    ):
        _load_public_surface_contract_from_payload(
            drifted_payload,
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
            schema_payload=drifted_schema,
        )

    drift_result = _run_node_contract_validation(
        f"""
const assert = require("node:assert/strict");
const {{ validateSharedPublicSurfaceSchemaShape }} = require("./bin/install.js");
const schema = {json.dumps(drifted_schema)};
assert.throws(
  () => validateSharedPublicSurfaceSchemaShape(schema),
  /public surface contract schema\\.sections\\.beginner_onboarding\\.keys must exactly match the code-supported public surface fields/
);
"""
    )

    assert drift_result.returncode == 0, f"{drift_result.stdout}\n{drift_result.stderr}"

    drifted_top_level_schema = json.loads(json.dumps(canonical_schema))
    drifted_top_level_schema["top_level_keys"].append("legacy_note")
    top_level_result = _run_node_contract_validation(
        f"""
const assert = require("node:assert/strict");
const {{ validateSharedPublicSurfaceSchemaShape }} = require("./bin/install.js");
const schema = {json.dumps(drifted_top_level_schema)};
assert.throws(
  () => validateSharedPublicSurfaceSchemaShape(schema),
  /public surface contract schema\\.top_level_keys must exactly match the code-supported public surface fields/
);
"""
    )

    assert top_level_result.returncode == 0, f"{top_level_result.stdout}\n{top_level_result.stderr}"


def test_bootstrap_runtime_catalog_validator_rejects_malformed_records() -> None:
    result = _run_node_contract_validation(
        r"""
const assert = require("node:assert/strict");
const { validateRuntimeCatalog } = require("./bin/install.js");
const catalog = require("./src/gpd/adapters/runtime_catalog.json");
const runtimeCatalogSchema = require("./src/gpd/adapters/runtime_catalog_schema.json");
const installHelpExampleScopes = new Set(runtimeCatalogSchema.install_help_example_scopes);
const installHelpExampleScopeList = [...installHelpExampleScopes].sort();
const launchWrapperPermissionSurfaceKinds = [...new Set(runtimeCatalogSchema.launch_wrapper_permission_surface_kinds)].sort();
const launchWrapperDisjunction = launchWrapperPermissionSurfaceKinds.length === 1
  ? JSON.stringify(launchWrapperPermissionSurfaceKinds[0])
  : `one of ${launchWrapperPermissionSurfaceKinds.map((value) => JSON.stringify(value)).join(", ")}`;
const escapeRegex = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

assert.doesNotThrow(() => validateRuntimeCatalog(catalog));

const helpExampleRuntimes = catalog.filter((runtime) => runtime.installer_help_example_scope);
assert.ok(helpExampleRuntimes.length >= 2);
for (const runtime of helpExampleRuntimes) {
  assert.ok(installHelpExampleScopes.has(runtime.installer_help_example_scope));
  if (runtime.installer_help_example_scope === "global") {
    assert.equal(runtime.validated_command_surface, "public_runtime_slash_command");
    continue;
  }
  if (runtime.installer_help_example_scope === "local") {
    assert.equal(runtime.validated_command_surface, "public_runtime_dollar_command");
  }
}
if (installHelpExampleScopes.has("global")) {
  assert.ok(helpExampleRuntimes.some((runtime) => runtime.installer_help_example_scope === "global"));
}
if (installHelpExampleScopes.has("local")) {
  assert.ok(helpExampleRuntimes.some((runtime) => runtime.installer_help_example_scope === "local"));
}

const duplicateGlobalHelpScopeCatalog = JSON.parse(JSON.stringify(catalog));
const runtimeWithoutGlobalHelpScope = duplicateGlobalHelpScopeCatalog.find(
  (runtime) => runtime.installer_help_example_scope !== "global"
);
assert.ok(runtimeWithoutGlobalHelpScope);
runtimeWithoutGlobalHelpScope.installer_help_example_scope = "global";
assert.throws(
  () => validateRuntimeCatalog(duplicateGlobalHelpScopeCatalog),
  /runtime catalog contains duplicate installer_help_example_scope "global"/
);

const duplicateLocalHelpScopeCatalog = JSON.parse(JSON.stringify(catalog));
const runtimeWithoutLocalHelpScope = duplicateLocalHelpScopeCatalog.find(
  (runtime) => runtime.installer_help_example_scope !== "local"
);
assert.ok(runtimeWithoutLocalHelpScope);
runtimeWithoutLocalHelpScope.installer_help_example_scope = "local";
assert.throws(
  () => validateRuntimeCatalog(duplicateLocalHelpScopeCatalog),
  /runtime catalog contains duplicate installer_help_example_scope "local"/
);

const explicitSurfaceCatalog = JSON.parse(JSON.stringify(catalog));
explicitSurfaceCatalog[0].public_command_surface_prefix = explicitSurfaceCatalog[0].command_prefix;
const validatedSurfaceCatalog = validateRuntimeCatalog(explicitSurfaceCatalog);
assert.equal(
  validatedSurfaceCatalog[0].public_command_surface_prefix,
  explicitSurfaceCatalog[0].command_prefix
);

const unknownKeyCatalog = JSON.parse(JSON.stringify(catalog));
unknownKeyCatalog[0].legacy_note = "unexpected";
assert.throws(
  () => validateRuntimeCatalog(unknownKeyCatalog),
  /runtime catalog entry 0 contains unknown key\(s\): legacy_note/
);

const blankAliasCatalog = JSON.parse(JSON.stringify(catalog));
blankAliasCatalog[0].selection_aliases = [blankAliasCatalog[0].selection_aliases[0], " "];
assert.throws(
  () => validateRuntimeCatalog(blankAliasCatalog),
  /runtime catalog entry 0\.selection_aliases\[1\] must be a non-empty string/
);

const badFlagCatalog = JSON.parse(JSON.stringify(catalog));
badFlagCatalog[0].native_include_support = "true";
assert.throws(
  () => validateRuntimeCatalog(badFlagCatalog),
  /runtime catalog entry 0\.native_include_support must be a boolean/
);

const badHelpScopeCatalog = JSON.parse(JSON.stringify(catalog));
badHelpScopeCatalog[0].installer_help_example_scope = "sideways";
assert.throws(
  () => validateRuntimeCatalog(badHelpScopeCatalog),
  new RegExp(
    `runtime catalog entry 0\\.installer_help_example_scope must be one of: ${escapeRegex(installHelpExampleScopeList.join(", "))}`
  )
);

const badSurfaceCatalog = JSON.parse(JSON.stringify(catalog));
badSurfaceCatalog[0].validated_command_surface = "hex-command";
assert.throws(
  () => validateRuntimeCatalog(badSurfaceCatalog),
  /runtime catalog entry 0\.validated_command_surface must match \/\^public_runtime_\[a-z0-9_\]\+_command\$\/$/
);

const futureSurfaceCatalog = JSON.parse(JSON.stringify(catalog));
futureSurfaceCatalog[0].validated_command_surface = "public_runtime_semicolon_command";
assert.equal(validateRuntimeCatalog(futureSurfaceCatalog)[0].validated_command_surface, "public_runtime_semicolon_command");

const reversedCatalog = JSON.parse(JSON.stringify(catalog)).reverse();
const sortedCatalog = validateRuntimeCatalog(reversedCatalog);
for (let index = 1; index < sortedCatalog.length; index += 1) {
  const previous = sortedCatalog[index - 1];
  const current = sortedCatalog[index];
  assert.ok(
    previous.priority < current.priority ||
      (previous.priority === current.priority && previous.runtime_name <= current.runtime_name),
    `runtime catalog order drifted at index ${index}`
  );
}

const duplicateRuntimeNameCatalog = JSON.parse(JSON.stringify(catalog));
duplicateRuntimeNameCatalog[1].runtime_name = duplicateRuntimeNameCatalog[0].runtime_name;
assert.throws(
  () => validateRuntimeCatalog(duplicateRuntimeNameCatalog),
  /runtime catalog contains duplicate runtime_name/
);

const duplicateFlagCatalog = JSON.parse(JSON.stringify(catalog));
duplicateFlagCatalog[1].selection_flags = [duplicateFlagCatalog[0].selection_flags[0]];
assert.throws(
  () => validateRuntimeCatalog(duplicateFlagCatalog),
  /runtime catalog contains duplicate selection flag/
);

const duplicateAliasCatalog = JSON.parse(JSON.stringify(catalog));
duplicateAliasCatalog[1].selection_aliases = [duplicateAliasCatalog[0].selection_aliases[0]];
assert.throws(
  () => validateRuntimeCatalog(duplicateAliasCatalog),
  /runtime catalog contains duplicate runtime selection token/
);

const duplicateInstallFlagCatalog = JSON.parse(JSON.stringify(catalog));
duplicateInstallFlagCatalog[1].install_flag = duplicateInstallFlagCatalog[0].install_flag;
assert.throws(
  () => validateRuntimeCatalog(duplicateInstallFlagCatalog),
  /runtime catalog contains duplicate install_flag/
);

const badTelemetryCatalog = JSON.parse(JSON.stringify(catalog));
badTelemetryCatalog[0].capabilities.telemetry_source = "webhook";
assert.throws(
  () => validateRuntimeCatalog(badTelemetryCatalog),
  /runtime catalog entry 0\.capabilities\.telemetry_source must be one of: none, notify-hook/
);

const futureConfigSurfaceCatalog = JSON.parse(JSON.stringify(catalog));
futureConfigSurfaceCatalog[0].capabilities.permission_surface_kind = "future.json:permissions.mode";
futureConfigSurfaceCatalog[0].capabilities.statusline_config_surface = "future.json:statusLine";
futureConfigSurfaceCatalog[0].capabilities.notify_config_surface = "future.json:notify";
const validatedConfigSurfaceCatalog = validateRuntimeCatalog(futureConfigSurfaceCatalog);
assert.equal(
  validatedConfigSurfaceCatalog[0].capabilities.permission_surface_kind,
  "future.json:permissions.mode"
);
assert.equal(
  validatedConfigSurfaceCatalog[0].capabilities.statusline_config_surface,
  "future.json:statusLine"
);
assert.equal(
  validatedConfigSurfaceCatalog[0].capabilities.notify_config_surface,
  "future.json:notify"
);

const futureLaunchWrapperPermissionKindCatalog = JSON.parse(JSON.stringify(catalog));
const launchWrapperRuntime = futureLaunchWrapperPermissionKindCatalog.find(
  (runtime) => runtime.capabilities.permissions_surface === "launch-wrapper"
);
launchWrapperRuntime.capabilities.permission_surface_kind = "future.json:launchWrapper";
assert.throws(
  () => validateRuntimeCatalog(futureLaunchWrapperPermissionKindCatalog),
  new RegExp(
    `runtime catalog entry \\d+\\.capabilities\\.permission_surface_kind must be ${escapeRegex(launchWrapperDisjunction)} when permissions_surface=launch-wrapper`
  )
);

const badPermissionKindCatalog = JSON.parse(JSON.stringify(catalog));
badPermissionKindCatalog[0].capabilities.permission_surface_kind = "approval-toggle";
assert.throws(
  () => validateRuntimeCatalog(badPermissionKindCatalog),
  new RegExp(
    `runtime catalog entry 0\\.capabilities\\.permission_surface_kind must be "none", ${escapeRegex(launchWrapperDisjunction)}, or a config surface label like file:key`
  )
);

const badStatuslineCatalog = JSON.parse(JSON.stringify(catalog));
badStatuslineCatalog[0].capabilities.statusline_surface = "implicit";
assert.throws(
  () => validateRuntimeCatalog(badStatuslineCatalog),
  /runtime catalog entry 0\.capabilities\.statusline_surface must be one of: explicit, none/
);

const badStatuslineConfigCatalog = JSON.parse(JSON.stringify(catalog));
badStatuslineConfigCatalog[0].capabilities.statusline_config_surface = "statusLine-toggle";
assert.throws(
  () => validateRuntimeCatalog(badStatuslineConfigCatalog),
  /runtime catalog entry 0\.capabilities\.statusline_config_surface must be "none" or a config surface label like file:key/
);

const badNotifyConfigCatalog = JSON.parse(JSON.stringify(catalog));
badNotifyConfigCatalog[0].capabilities.notify_config_surface = "notify-toggle";
assert.throws(
  () => validateRuntimeCatalog(badNotifyConfigCatalog),
  /runtime catalog entry 0\.capabilities\.notify_config_surface must be "none" or a config surface label like file:key/
);

const badConfigFilePermissionContractCatalog = JSON.parse(JSON.stringify(catalog));
badConfigFilePermissionContractCatalog[0].capabilities.permissions_surface = "config-file";
badConfigFilePermissionContractCatalog[0].capabilities.permission_surface_kind = "none";
assert.throws(
  () => validateRuntimeCatalog(badConfigFilePermissionContractCatalog),
  /runtime catalog entry 0\.capabilities\.permission_surface_kind must be a config surface label when permissions_surface=config-file/
);

const badConfigFileSpecialValueCatalog = JSON.parse(JSON.stringify(catalog));
badConfigFileSpecialValueCatalog[0].capabilities.permissions_surface = "config-file";
badConfigFileSpecialValueCatalog[0].capabilities.permission_surface_kind = launchWrapperPermissionSurfaceKinds[0];
assert.throws(
  () => validateRuntimeCatalog(badConfigFileSpecialValueCatalog),
  /runtime catalog entry 0\.capabilities\.permission_surface_kind must be a config surface label when permissions_surface=config-file/
);

const badUnsupportedPermissionContractCatalog = JSON.parse(JSON.stringify(catalog));
badUnsupportedPermissionContractCatalog[0].capabilities.permissions_surface = "unsupported";
badUnsupportedPermissionContractCatalog[0].capabilities.permission_surface_kind = "future.json:permissions.mode";
badUnsupportedPermissionContractCatalog[0].capabilities.supports_runtime_permission_sync = true;
badUnsupportedPermissionContractCatalog[0].capabilities.supports_prompt_free_mode = false;
badUnsupportedPermissionContractCatalog[0].capabilities.prompt_free_requires_relaunch = false;
assert.throws(
  () => validateRuntimeCatalog(badUnsupportedPermissionContractCatalog),
  /runtime catalog entry 0\.capabilities\.permission_surface_kind must be "none" when permissions_surface=unsupported/
);

const mismatchedSurfaceCatalog = JSON.parse(JSON.stringify(catalog));
mismatchedSurfaceCatalog[0].public_command_surface_prefix = `${mismatchedSurfaceCatalog[0].command_prefix}x`;
assert.throws(
  () => validateRuntimeCatalog(mismatchedSurfaceCatalog),
  /runtime catalog entry 0\.public_command_surface_prefix must match command_prefix/
);
"""
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"


def test_bootstrap_runtime_catalog_validator_stays_in_parity_with_python_loader(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    canonical_payload = json.loads((REPO_ROOT / "src" / "gpd" / "adapters" / "runtime_catalog.json").read_text(encoding="utf-8"))
    python_descriptors = _iter_runtime_descriptors_from_payload(canonical_payload, tmp_path=tmp_path, monkeypatch=monkeypatch)

    assert [descriptor.runtime_name for descriptor in python_descriptors] == [
        descriptor.runtime_name for descriptor in iter_runtime_descriptors()
    ]
    assert python_descriptors[0].install_flag == iter_runtime_descriptors()[0].install_flag

    canonical_result = _run_node_contract_validation(
        f"""
const assert = require("node:assert/strict");
const {{ validateRuntimeCatalog }} = require("./bin/install.js");
const catalog = {json.dumps(canonical_payload)};
const normalized = validateRuntimeCatalog(catalog);
assert.equal(normalized[0].runtime_name, catalog[0].runtime_name);
assert.equal(normalized[0].install_flag, catalog[0].install_flag);
assert.equal(normalized[normalized.length - 1].runtime_name, catalog[catalog.length - 1].runtime_name);
"""
    )
    assert canonical_result.returncode == 0, f"{canonical_result.stdout}\n{canonical_result.stderr}"

    additive_payload = json.loads((REPO_ROOT / "src" / "gpd" / "adapters" / "runtime_catalog.json").read_text(encoding="utf-8"))
    additive_payload[0]["legacy_note"] = "unexpected"
    with pytest.raises(ValueError, match=r"runtime catalog entry 0 contains unknown key\(s\): legacy_note"):
        _iter_runtime_descriptors_from_payload(additive_payload, tmp_path=tmp_path, monkeypatch=monkeypatch)
    additive_result = _run_node_contract_validation(
        f"""
const assert = require("node:assert/strict");
const {{ validateRuntimeCatalog }} = require("./bin/install.js");
const catalog = {json.dumps(additive_payload)};
assert.throws(() => validateRuntimeCatalog(catalog), /runtime catalog entry 0 contains unknown key\\(s\\): legacy_note/);
"""
    )
    assert additive_result.returncode == 0, f"{additive_result.stdout}\n{additive_result.stderr}"

    duplicate_payload = json.loads((REPO_ROOT / "src" / "gpd" / "adapters" / "runtime_catalog.json").read_text(encoding="utf-8"))
    duplicate_payload[1]["install_flag"] = duplicate_payload[0]["install_flag"]
    with pytest.raises(ValueError, match=r"runtime catalog contains duplicate install_flag"):
        _iter_runtime_descriptors_from_payload(duplicate_payload, tmp_path=tmp_path, monkeypatch=monkeypatch)
    duplicate_result = _run_node_contract_validation(
        f"""
const assert = require("node:assert/strict");
const {{ validateRuntimeCatalog }} = require("./bin/install.js");
const catalog = {json.dumps(duplicate_payload)};
assert.throws(() => validateRuntimeCatalog(catalog), /runtime catalog contains duplicate install_flag/);
"""
    )
    assert duplicate_result.returncode == 0, f"{duplicate_result.stdout}\n{duplicate_result.stderr}"


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_help_uses_catalog_driven_example_runtimes() -> None:
    node_path = shutil.which("node")
    assert node_path is not None

    result = subprocess.run(
        [node_path, "bin/install.js", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    for descriptor in _RUNTIME_HELP_EXAMPLE_DESCRIPTORS:
        assert (
            f"# Install for {descriptor.display_name} {descriptor.installer_help_example_scope}" in result.stdout
        )
    assert "startsWith(\"$\")" not in result.stdout


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
    assert "Install Summary" in result.stdout
    assert "Startup checklist" in result.stdout
    assert "Beginner Onboarding Hub:" in result.stdout
    assert _BEGINNER_ONBOARDING_HUB_URL in result.stdout
    _assert_single_runtime_next_steps(result.stdout, _CODEX_RUNTIME_NAME)
    assert f"Installing GPD for {_RUNTIME_DISPLAY_NAMES[_CODEX_RUNTIME_NAME]} (local)..." not in result.stdout
    assert f"Installed GPD for {_RUNTIME_DISPLAY_NAMES[_CODEX_RUNTIME_NAME]} (local)." not in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bootstrap installer harness uses POSIX-style fake Python shims")
@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for bootstrap installer tests")
def test_bootstrap_fake_python_harness_ignores_ambient_fake_pip_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAKE_PIP_FAIL_PYPI", "1")

    result, _home, _log_path = _run_bootstrap_with_fake_python(tmp_path)

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"


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
    assert f"`gpd doctor --runtime {_CODEX_RUNTIME_NAME} --local --target-dir " in result.stdout
    assert f"{_RUNTIME_ADAPTERS[_CODEX_RUNTIME_NAME].config_dir_name}`" in result.stdout


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
    assert "git checkout could not resolve branch main" in result.stderr
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
    assert "Startup checklist" in result.stdout
    assert "Beginner Onboarding Hub:" in result.stdout
    assert _BEGINNER_ONBOARDING_HUB_URL in result.stdout
    for runtime in _RUNTIME_NAMES:
        _assert_multi_runtime_next_steps_line(result.stdout, runtime)
    _assert_install_summary_semantic_contract(
        result.stdout,
        runtime_help_fragments=tuple(_RUNTIME_HELP_COMMANDS[runtime] for runtime in _RUNTIME_NAMES),
        resume_work_fragments=("your runtime-specific `resume-work` command",),
        suggest_next_fragments=("your runtime-specific `suggest-next` command",),
        pause_work_fragments=("your runtime-specific `pause-work` command",),
    )


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
    combined_output = result.stdout + result.stderr
    assert "PyPI install failed. Falling back to GitHub source..." in combined_output
    assert f"Detected that GitHub source archive for v{PYTHON_PACKAGE_VERSION} is unavailable: HTTP 404." in combined_output
    assert f"Installing GPD from HTTPS git checkout for v{PYTHON_PACKAGE_VERSION} into the managed environment..." in combined_output


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
    managed_pip_targets = [
        entry["argv"][-1]
        for entry in entries
        if entry["managed"] and entry["argv"][:4] == ["-m", "pip", "install", "--upgrade"]
    ]

    assert managed_pip_targets == [PYPI_SPEC]
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
    managed_pip_targets = [
        entry["argv"][-1]
        for entry in entries
        if entry["managed"] and entry["argv"][:4] == ["-m", "pip", "install", "--upgrade"]
    ]

    assert managed_pip_targets == [PYPI_SPEC]
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
