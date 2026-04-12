"""Prompt-hygiene guardrails for key command wrappers."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from gpd.adapters.runtime_catalog import iter_runtime_descriptors

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
PROMPT_SOURCE_DIRS = (COMMANDS_DIR, WORKFLOWS_DIR)


def _runtime_config_dir_pattern() -> re.Pattern[str]:
    runtime_dirs: set[str] = set()
    for descriptor in iter_runtime_descriptors():
        for value in (descriptor.config_dir_name, descriptor.global_config.home_subpath):
            if value:
                runtime_dirs.add(value.strip("/"))
    if not runtime_dirs:
        return re.compile(r"$^")
    escaped = "|".join(re.escape(value) for value in sorted(runtime_dirs))
    return re.compile(rf"~/(?:{escaped})(?:/|$)")


MACHINE_SPECIFIC_PATH_PATTERNS = (
    re.compile(r"/Users/"),
    re.compile(r"/home/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
    re.compile(r"~/\\.agents/"),
    _runtime_config_dir_pattern(),
)


def _commands_with_matching_workflows() -> list[str]:
    return sorted(
        command_path.stem
        for command_path in COMMANDS_DIR.glob("*.md")
        if (WORKFLOWS_DIR / command_path.name).exists()
    )


def _prompt_source_paths() -> list[Path]:
    return sorted(path for directory in PROMPT_SOURCE_DIRS for path in directory.glob("*.md"))


def test_commands_reference_their_workflow_file_once() -> None:
    for command in _commands_with_matching_workflows():
        prompt = (COMMANDS_DIR / f"{command}.md").read_text(encoding="utf-8")
        workflow_ref = f"@{{GPD_INSTALL_DIR}}/workflows/{command}.md"
        assert prompt.count(workflow_ref) in {1, 2}


def test_workflows_do_not_repeat_runtime_delegation_note() -> None:
    delegation_note = "runtime-delegation-note.md"
    offenders = {}
    for path in WORKFLOWS_DIR.glob("*.md"):
        count = path.read_text(encoding="utf-8").count(delegation_note)
        if count > 1:
            offenders[path.name] = count

    assert offenders == {}


def test_prompt_sources_do_not_embed_machine_specific_absolute_paths() -> None:
    offenders: dict[str, list[str]] = {}

    for path in _prompt_source_paths():
        matches = [
            pattern.pattern
            for pattern in MACHINE_SPECIFIC_PATH_PATTERNS
            if pattern.search(path.read_text(encoding="utf-8"))
        ]
        if matches:
            offenders[path.relative_to(REPO_ROOT).as_posix()] = matches

    assert offenders == {}


def test_command_sources_do_not_repeat_exact_include_markers() -> None:
    offenders: dict[str, dict[str, int]] = {}

    for path in COMMANDS_DIR.glob("*.md"):
        include_lines = [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip().startswith("@{GPD_INSTALL_DIR}/")
        ]
        duplicates = {
            line: count
            for line, count in Counter(include_lines).items()
            if count > 1
        }
        if duplicates:
            offenders[path.name] = duplicates

    assert offenders == {}


def test_plan_phase_prompt_documents_inline_discuss_flag() -> None:
    prompt = (COMMANDS_DIR / "plan-phase.md").read_text(encoding="utf-8")
    assert "--inline-discuss" in prompt
    assert "Combine discuss-phase and plan-phase" in prompt


def test_debug_prompt_process_section_is_terminal() -> None:
    prompt = (COMMANDS_DIR / "debug.md").read_text(encoding="utf-8")
    assert prompt.rstrip().endswith("</process>")


def test_execute_phase_prompt_has_no_context_budget_reference_tail() -> None:
    prompt = (COMMANDS_DIR / "execute-phase.md").read_text(encoding="utf-8")
    assert "context-budget reference" not in prompt


def test_commands_omit_removed_verify_between_waves_term() -> None:
    term = "verify-between-waves"
    offenders: list[str] = []
    for path in COMMANDS_DIR.glob("*.md"):
        if term in path.read_text(encoding="utf-8"):
            offenders.append(path.name)

    assert offenders == []
