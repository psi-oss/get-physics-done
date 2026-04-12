"""Regression test for command prompt boilerplate cleanup."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
AGENT_INFRASTRUCTURE = REPO_ROOT / "src" / "gpd" / "specs" / "references" / "orchestration" / "agent-infrastructure.md"
WORKFLOW_SPECS = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"

LEGACY_COMMENT_FRAGMENTS = (
    "Tool names and @ includes are platform-specific.",
    "Allowed-tools are runtime-specific.",
    "Tool names and @ includes are runtime-specific.",
)

MODEL_FACING_DIRS = (COMMANDS_DIR, AGENTS_DIR, WORKFLOW_SPECS)

UNRESOLVED_PLACEHOLDER_RE = re.compile(r"(?:^|\n)\s*(?:<!--\s*)?(?:TODO|FIXME|PLACEHOLDER)(?:\b|:)")

LEGACY_BACKCOMPAT_WORDING = (
    "backcompat",
    "back-compat",
    "backward compatibility",
    "backwards compatibility",
)

THIN_WORKFLOW_WRAPPERS = (
    "error-propagation",
    "numerical-convergence",
    "parameter-sweep",
    "sensitivity-analysis",
)


def test_model_facing_sources_do_not_keep_runtime_boilerplate_html_comments() -> None:
    for directory in MODEL_FACING_DIRS:
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            for fragment in LEGACY_COMMENT_FRAGMENTS:
                assert fragment not in text, f"{path.relative_to(REPO_ROOT)} still contains: {fragment}"


def test_model_facing_prompts_do_not_ship_unresolved_placeholders() -> None:
    for directory in MODEL_FACING_DIRS:
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            assert not UNRESOLVED_PLACEHOLDER_RE.search(text), (
                f"{path.relative_to(REPO_ROOT)} still contains an unresolved placeholder marker"
            )


def test_model_facing_prompts_do_not_use_legacy_backcompat_wording() -> None:
    for directory in MODEL_FACING_DIRS:
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8").lower()
            for phrase in LEGACY_BACKCOMPAT_WORDING:
                assert phrase not in text, f"{path.relative_to(REPO_ROOT)} still contains {phrase}"


def test_standardized_thin_workflow_wrappers_stay_concise() -> None:
    process_block_re = re.compile(r"<process>(.*?)</process>", re.S)
    exec_context_re = re.compile(r"<execution_context>(.*?)</execution_context>", re.S)
    keep_line = "Keep this command wrapper thin; the workflow owns detailed method guidance."
    rest_line = "Do not restate workflow-owned checklists or compatibility policy here."
    exec_context_reminder = "Read the workflow referenced in `<execution_context>` with `file_read` first."

    for stem in THIN_WORKFLOW_WRAPPERS:
        path = COMMANDS_DIR / f"{stem}.md"
        text = path.read_text(encoding="utf-8")
        body_lines = [
            line
            for line in text.splitlines()
            if line.strip() and not line.strip().startswith("---") and not re.match(r"^[a-z_]+:", line.strip())
        ]

        assert len(body_lines) <= 25, f"{path.relative_to(REPO_ROOT)} grew beyond thin-wrapper policy"

        exec_match = exec_context_re.search(text)
        assert exec_match is not None, f"{path.relative_to(REPO_ROOT)} missing execution_context"
        execution_context_text = exec_match.group(1).strip()
        workflow_link = f"@{{GPD_INSTALL_DIR}}/workflows/{stem}.md"
        assert execution_context_text == workflow_link, path

        process_match = process_block_re.search(text)
        assert process_match is not None, f"{path.relative_to(REPO_ROOT)} missing process block"
        process_text = process_match.group(1).strip()
        if process_text.startswith(exec_context_reminder):
            process_text = process_text[len(exec_context_reminder) :].lstrip()
        if process_text.startswith("CONTEXT=$(gpd --raw validate command-context "):
            _, _, process_text = process_text.partition("\n")
            process_text = process_text.lstrip()
            if process_text.startswith(exec_context_reminder):
                process_text = process_text[len(exec_context_reminder) :].lstrip()
        assert process_text.startswith(keep_line), path
        assert rest_line in process_text, path
        assert process_text.count(workflow_link) == 0, path


def test_process_blocks_do_not_duplicate_workflow_paths() -> None:
    process_block_re = re.compile(r"<process>(.*?)</process>", re.S)
    for path in sorted(COMMANDS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        match = process_block_re.search(text)
        assert match is not None, f"{path.relative_to(REPO_ROOT)} missing process block"
        process_text = match.group(1)
        if path.stem in THIN_WORKFLOW_WRAPPERS:
            assert "@{GPD_INSTALL_DIR}/workflows/" not in process_text, (
                f"{path.relative_to(REPO_ROOT)} still duplicates workflow path in <process>"
            )


def test_consistency_checker_uses_canonical_gpd_return_fields() -> None:
    path = AGENTS_DIR / "gpd-consistency-checker.md"
    text = path.read_text(encoding="utf-8")
    assert "phase_checked" not in text
    assert "  phase: [phase or milestone scope]" in text
    assert "  field_assessment:" in text
    assert "    checks_performed: [count]" in text
    assert "    issues_found: [count]" in text


def test_agent_infrastructure_uses_runtime_neutral_delegation_language() -> None:
    text = AGENT_INFRASTRUCTURE.read_text(encoding="utf-8")
    assert "Agent Delegation Checklist" in text
    assert "Before delegating to any agent" in text
    assert "Before spawning any agent" not in text
    assert "Spawning unnecessary agents" not in text
