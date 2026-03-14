"""Guardrails that keep prompt-authored CLI references aligned with the real CLI."""

from __future__ import annotations

import re
from pathlib import Path

from gpd.registry import VALID_CONTEXT_MODES, _parse_frontmatter

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_PATH = REPO_ROOT / "src/gpd/cli.py"
PROMPT_ROOTS = (
    REPO_ROOT / "src/gpd/commands",
    REPO_ROOT / "src/gpd/agents",
    REPO_ROOT / "src/gpd/specs/workflows",
    REPO_ROOT / "src/gpd/specs/references",
    REPO_ROOT / "src/gpd/specs/templates",
)
GRAPH_PATH = REPO_ROOT / "tests" / "README.md"

INIT_COMMAND_RE = re.compile(r"@init_app\.command\(\s*\"([a-z0-9-]+)\"(?:,|\))", re.MULTILINE)
INIT_USAGE_RE = re.compile(r"\bgpd init ([a-z0-9-]+)\b")
VALIDATE_COMMAND_RE = re.compile(r"@validate_app\.command\(\s*\"([a-z0-9-]+)\"(?:,|\))", re.MULTILINE)
VALIDATE_USAGE_RE = re.compile(r"\bgpd(?:\s+--raw)?\s+validate\s+([a-z0-9-]+)\b")
NON_CANONICAL_GPD_COMMAND_RE = re.compile(r"(?<![A-Za-z0-9_./}])(?:\$gpd-[A-Za-z0-9{}-]+|/gpd-[A-Za-z0-9{}-]+)(?!\.md)")
RAW_AFTER_SUBCOMMAND_RE = re.compile(r"\bgpd\s+(?!--raw\b)[^`\n]*\s+--raw\b")
SUMMARY_EXTRACT_FIELDS_RE = re.compile(r"\bgpd\s+summary-extract\b[^\n`]*\s--fields\b")


def _iter_prompt_sources() -> list[Path]:
    files: list[Path] = []
    for root in PROMPT_ROOTS:
        files.extend(sorted(root.rglob("*.md")))
    return files


def _declared_init_subcommands() -> set[str]:
    content = CLI_PATH.read_text(encoding="utf-8")
    return set(INIT_COMMAND_RE.findall(content))


def _declared_validate_subcommands() -> set[str]:
    content = CLI_PATH.read_text(encoding="utf-8")
    return set(VALIDATE_COMMAND_RE.findall(content))


def test_prompt_sources_use_only_real_gpd_init_subcommands() -> None:
    allowed = _declared_init_subcommands()
    invalid: list[str] = []

    for path in _iter_prompt_sources():
        content = path.read_text(encoding="utf-8")
        for match in INIT_USAGE_RE.finditer(content):
            subcommand = match.group(1)
            if subcommand not in allowed:
                invalid.append(f"{path.relative_to(REPO_ROOT)} -> {subcommand}")

    assert invalid == []


def test_prompt_sources_use_only_real_gpd_validate_subcommands() -> None:
    allowed = _declared_validate_subcommands()
    invalid: list[str] = []

    for path in _iter_prompt_sources():
        content = path.read_text(encoding="utf-8")
        for match in VALIDATE_USAGE_RE.finditer(content):
            subcommand = match.group(1)
            if subcommand not in allowed:
                invalid.append(f"{path.relative_to(REPO_ROOT)} -> {subcommand}")

    assert invalid == []


def test_prompt_sources_use_canonical_gpd_command_syntax() -> None:
    invalid: list[str] = []

    for path in _iter_prompt_sources():
        content = path.read_text(encoding="utf-8")
        for match in NON_CANONICAL_GPD_COMMAND_RE.finditer(content):
            invalid.append(f"{path.relative_to(REPO_ROOT)} -> {match.group(0)}")

    assert invalid == []


def test_help_prompt_command_count_matches_live_inventory() -> None:
    command_count = len(list((REPO_ROOT / "src/gpd/commands").glob("*.md")))
    help_prompt = (REPO_ROOT / "src/gpd/commands/help.md").read_text(encoding="utf-8")

    assert f"Run `/gpd:help --all` for all {command_count} commands." in help_prompt


def test_suggest_next_prompt_uses_real_cli_subcommand() -> None:
    suggest_prompt = (REPO_ROOT / "src/gpd/commands/suggest-next.md").read_text(encoding="utf-8")

    assert "Uses `gpd --raw suggest`" in suggest_prompt
    assert "gpd suggest-next to scan" not in suggest_prompt


def test_doc_sources_place_global_raw_before_subcommands() -> None:
    invalid: list[str] = []
    doc_paths = [*(_iter_prompt_sources()), GRAPH_PATH]

    for path in doc_paths:
        content = path.read_text(encoding="utf-8")
        for match in RAW_AFTER_SUBCOMMAND_RE.finditer(content):
            invalid.append(f"{path.relative_to(REPO_ROOT)} -> {match.group(0)}")

    assert invalid == []


def test_command_prompts_declare_valid_context_modes() -> None:
    missing: list[str] = []
    invalid: list[str] = []

    for path in sorted((REPO_ROOT / "src/gpd/commands").glob("*.md")):
        meta, _body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        mode = meta.get("context_mode")
        if mode is None:
            missing.append(str(path.relative_to(REPO_ROOT)))
            continue
        if str(mode) not in VALID_CONTEXT_MODES:
            invalid.append(f"{path.relative_to(REPO_ROOT)} -> {mode}")

    assert missing == []
    assert invalid == []


def test_prompt_sources_use_summary_extract_field_flag_not_fields() -> None:
    invalid: list[str] = []
    doc_paths = [*(_iter_prompt_sources()), GRAPH_PATH]

    for path in doc_paths:
        content = path.read_text(encoding="utf-8")
        for match in SUMMARY_EXTRACT_FIELDS_RE.finditer(content):
            invalid.append(f"{path.relative_to(REPO_ROOT)} -> {match.group(0)}")

    assert invalid == []


def test_new_project_prompt_uses_stdin_for_contract_validation_and_persistence() -> None:
    workflow = (REPO_ROOT / "src/gpd/specs/workflows/new-project.md").read_text(encoding="utf-8")

    assert 'printf \'%s\\n\' "$PROJECT_CONTRACT_JSON" | gpd --raw validate project-contract -' in workflow
    assert 'printf \'%s\\n\' "$PROJECT_CONTRACT_JSON" | gpd state set-project-contract -' in workflow
    assert "/tmp/gpd-project-contract.json" not in workflow
    assert "temporary JSON file if needed" not in workflow


def test_state_json_schema_stays_aligned_with_stdin_contract_persistence_flow() -> None:
    schema = (REPO_ROOT / "src/gpd/specs/templates/state-json-schema.md").read_text(encoding="utf-8")

    assert 'printf \'%s\\n\' "$PROJECT_CONTRACT_JSON" | gpd --raw validate project-contract -' in schema
    assert 'printf \'%s\\n\' "$PROJECT_CONTRACT_JSON" | gpd state set-project-contract -' in schema
    assert "Preferred write path: `gpd state set-project-contract <path-to-contract.json>`." not in schema


def test_compare_branches_prompt_keeps_branch_summary_extraction_in_memory() -> None:
    workflow = (REPO_ROOT / "src/gpd/specs/workflows/compare-branches.md").read_text(encoding="utf-8")

    assert "Prefer parsing the `git show` output directly in memory." in workflow
    assert "do not write it to `.gpd/tmp/` just to run a path-based extractor." in workflow
    assert "Keep branch-summary extraction in memory/stdout only" in workflow
    assert "do not use `.gpd/tmp/`, `/tmp`, or another temp root for this step." in workflow
