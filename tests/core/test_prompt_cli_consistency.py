"""Guardrails that keep prompt-authored CLI references aligned with the real CLI."""

from __future__ import annotations

import re
from pathlib import Path

from gpd.registry import VALID_CONTEXT_MODES, _parse_frontmatter

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_PATH = REPO_ROOT / "src/gpd/cli.py"
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
PROMPT_ROOTS = (
    COMMANDS_DIR,
    REPO_ROOT / "src/gpd/agents",
    WORKFLOWS_DIR,
    REPO_ROOT / "src/gpd/specs/references",
    REPO_ROOT / "src/gpd/specs/templates",
)
GRAPH_PATH = REPO_ROOT / "tests" / "README.md"

ROOT_COMMAND_RE = re.compile(r"@app\.command\(\s*\"([a-z0-9-]+)\"(?:,|\))", re.MULTILINE)
TYPER_GROUP_RE = re.compile(r"app\.add_typer\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*name=\"([a-z0-9-]+)\"", re.MULTILINE)
GROUP_COMMAND_RE = re.compile(r"@{group}\.command\(\s*\"([a-z0-9-]+)\"(?:,|\))", re.MULTILINE)
NON_CANONICAL_GPD_COMMAND_RE = re.compile(r"(?<![A-Za-z0-9_./}])(?:\$gpd-[A-Za-z0-9{}-]+|/gpd-[A-Za-z0-9{}-]+)(?!\.md)")
RAW_AFTER_SUBCOMMAND_RE = re.compile(r"\bgpd\s+(?!--raw\b)[^`\n]*\s+--raw\b")
SUMMARY_EXTRACT_FIELDS_RE = re.compile(r"\bgpd\s+summary-extract\b[^\n`]*\s--fields\b")


def _extract_between(content: str, start_marker: str, end_marker: str) -> str:
    start = content.index(start_marker) + len(start_marker)
    end = content.index(end_marker, start)
    return content[start:end]


def _iter_prompt_sources() -> list[Path]:
    files: list[Path] = []
    for root in PROMPT_ROOTS:
        files.extend(sorted(root.rglob("*.md")))
    return files


def _declared_command_surfaces() -> set[str]:
    content = CLI_PATH.read_text(encoding="utf-8")
    surfaces = set(ROOT_COMMAND_RE.findall(content))
    surfaces.update(_declared_group_surfaces(content))
    return surfaces


def _declared_group_surfaces(content: str) -> set[str]:
    groups = dict(TYPER_GROUP_RE.findall(content))
    surfaces: set[str] = set(groups.values())
    for group_var, group_name in groups.items():
        command_re = re.compile(GROUP_COMMAND_RE.pattern.format(group=re.escape(group_var)), re.MULTILINE)
        for subcommand in command_re.findall(content):
            surfaces.add(f"{group_name} {subcommand}")
    return surfaces


def _declared_root_commands(content: str) -> set[str]:
    return set(ROOT_COMMAND_RE.findall(content))


def _declared_groups(content: str) -> dict[str, set[str]]:
    groups = dict(TYPER_GROUP_RE.findall(content))
    result: dict[str, set[str]] = {}
    for group_var, group_name in groups.items():
        command_re = re.compile(GROUP_COMMAND_RE.pattern.format(group=re.escape(group_var)), re.MULTILINE)
        result[group_name] = set(command_re.findall(content))
    return result


def _iter_markdown_code_samples(content: str) -> list[str]:
    samples: list[str] = []
    fenced_pattern = re.compile(r"```(?:[^\n`]*)\n(.*?)```", re.DOTALL)
    for match in fenced_pattern.finditer(content):
        samples.append(match.group(1))
    inline_source = fenced_pattern.sub("\n", content)
    samples.extend(re.findall(r"`([^`]+)`", inline_source))
    return samples


def _extract_gpd_command_surfaces(
    content: str,
    *,
    root_commands: set[str],
    group_commands: dict[str, set[str]],
) -> list[str]:
    command_roots = root_commands | set(group_commands)
    if not command_roots:
        return []

    root_pattern = "|".join(sorted((re.escape(root) for root in command_roots), key=len, reverse=True))
    prefix_pattern = r"(?:\s+(?:--raw|--cwd(?:=[^\s`]+)?|--cwd\s+[^\s`]+))*"
    pattern = re.compile(rf"\bgpd{prefix_pattern}\s+({root_pattern})(?:\s+([a-z0-9-]+))?")
    surfaces: list[str] = []
    for sample in _iter_markdown_code_samples(content):
        for match in pattern.finditer(sample):
            command = match.group(1)
            subcommand = match.group(2)
            if command in root_commands and command not in group_commands:
                surfaces.append(command)
                continue
            if command in group_commands:
                surfaces.append(command if subcommand is None else f"{command} {subcommand}")
    return surfaces


def test_prompt_sources_use_only_real_gpd_command_surfaces() -> None:
    allowed = _declared_command_surfaces()
    content = CLI_PATH.read_text(encoding="utf-8")
    root_commands = _declared_root_commands(content)
    group_commands = _declared_groups(content)
    invalid: list[str] = []

    for path in _iter_prompt_sources():
        content = path.read_text(encoding="utf-8")
        for surface in _extract_gpd_command_surfaces(content, root_commands=root_commands, group_commands=group_commands):
            if surface not in allowed:
                invalid.append(f"{path.relative_to(REPO_ROOT)} -> {surface}")

    assert invalid == []


def test_prompt_sources_use_canonical_gpd_command_syntax() -> None:
    invalid: list[str] = []

    for path in _iter_prompt_sources():
        content = path.read_text(encoding="utf-8")
        for match in NON_CANONICAL_GPD_COMMAND_RE.finditer(content):
            invalid.append(f"{path.relative_to(REPO_ROOT)} -> {match.group(0)}")

    assert invalid == []


def test_help_prompt_command_count_matches_live_inventory() -> None:
    command_count = len(list(COMMANDS_DIR.glob("*.md")))
    help_prompt = (REPO_ROOT / "src/gpd/commands/help.md").read_text(encoding="utf-8")

    assert f"Run `/gpd:help --all` for all {command_count} commands." in help_prompt


def test_help_prompt_default_quick_start_stays_runtime_surface_focused() -> None:
    help_prompt = (COMMANDS_DIR / "help.md").read_text(encoding="utf-8")
    quick_start = _extract_between(
        help_prompt,
        "## Step 2: Quick Start (Default Output)",
        "## Step 3: Full Command Reference (--all)",
    )

    assert "# GPD Command Reference" in quick_start
    assert "These `/gpd:*` entries are canonical in-runtime slash-command names" in quick_start
    assert "## Quick Start" in quick_start
    assert "Choose the path that matches your starting point:" in quick_start
    for section in (
        "**New work**",
        "**Existing work**",
        "**Returning work**",
        "**Tangents**",
        "**Local CLI bridge**",
        "**Unattended / autonomy setup**",
    ):
        assert section in quick_start
    for line in (
        "/gpd:new-project",
        "/gpd:new-project --minimal",
        "/gpd:map-research",
        "/gpd:resume-work",
        "gpd resume --recent",
        "gpd --help",
        "gpd permissions status --runtime <runtime> --autonomy balanced",
        "gpd permissions sync --runtime <runtime> --autonomy balanced",
        "gpd observe execution",
        "gpd cost",
        "gpd presets list",
        "gpd presets show <preset>",
        "/gpd:progress",
        "/gpd:suggest-next",
        "/gpd:tangent",
        "/gpd:settings",
        "/gpd:help --all",
    ):
        assert line in quick_start
    assert "**Core workflow:** new-project → discuss-phase → plan-phase → execute-phase → verify-work → repeat → complete-milestone" in quick_start
    assert "**Publication:** write-paper → peer-review → respond-to-referees → arxiv-submission" in quick_start
    assert "gpd init new-project" not in quick_start


def test_help_prompt_keeps_workflow_preset_readiness_on_local_cli_surface() -> None:
    help_command = (COMMANDS_DIR / "help.md").read_text(encoding="utf-8")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")
    quick_start = _extract_between(
        help_command,
        "## Step 2: Quick Start (Default Output)",
        "## Step 3: Full Command Reference (--all)",
    )

    assert "**Workflow presets**" in quick_start
    assert "Paper/manuscript workflows" in quick_start
    assert "gpd doctor --runtime <runtime> --local|--global" in quick_start
    assert "gpd presets list" in quick_start
    assert "gpd presets show <preset>" in quick_start
    assert "gpd presets apply <preset>" in quick_start
    assert "runtime-local LaTeX preset readiness" in quick_start
    for content in (help_command, help_workflow):
        assert (
            "Use `gpd --help` to inspect the executable local install/readiness/permissions/diagnostics surface directly."
            in content
        )
        assert "gpd permissions status --runtime <runtime> --autonomy balanced" in content
        assert "gpd permissions sync --runtime <runtime> --autonomy balanced" in content
        assert "gpd doctor --runtime <runtime> --local|--global" in content
        assert "Workflow presets" in content
        assert "gpd presets show <preset>" in content
        assert "gpd presets apply <preset>" in content
        assert "not stored as a separate preset block" in content
        assert "failed preset rows degrade that workflow rather than blocking the base install" in content


def test_suggest_next_prompt_uses_real_cli_subcommand() -> None:
    suggest_prompt = (REPO_ROOT / "src/gpd/commands/suggest-next.md").read_text(encoding="utf-8")

    assert "Uses `gpd --raw suggest`" in suggest_prompt
    assert "Local CLI fallback: `gpd --raw suggest`" in suggest_prompt
    assert "gpd suggest-next to scan" not in suggest_prompt


def test_tangent_prompt_routes_into_existing_workflows() -> None:
    tangent_command = (COMMANDS_DIR / "tangent.md").read_text(encoding="utf-8")
    tangent_workflow = (WORKFLOWS_DIR / "tangent.md").read_text(encoding="utf-8")

    assert "name: gpd:tangent" in tangent_command
    assert "@{GPD_INSTALL_DIR}/workflows/tangent.md" in tangent_command
    assert "/gpd:quick" in tangent_command
    assert "/gpd:add-todo" in tangent_command
    assert "/gpd:branch-hypothesis" in tangent_command

    for token in (
        "Stay on the main path",
        "Run a bounded quick check now",
        "Capture and defer",
        "Open a hypothesis branch",
        "{GPD_INSTALL_DIR}/workflows/quick.md",
        "{GPD_INSTALL_DIR}/workflows/add-todo.md",
        "{GPD_INSTALL_DIR}/workflows/branch-hypothesis.md",
    ):
        assert token in tangent_workflow


def test_progress_prompt_runs_preflight_after_init_context() -> None:
    command = (REPO_ROOT / "src/gpd/commands/progress.md").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / "src/gpd/specs/workflows/progress.md").read_text(encoding="utf-8")

    for content in (command, workflow):
        assert "INIT=$(gpd init progress --include state,roadmap,project,config)" in content
        assert "CONTEXT=$(gpd --raw validate command-context progress \"$ARGUMENTS\")" in content
        assert content.index("INIT=$(gpd init progress --include state,roadmap,project,config)") < content.index(
            "CONTEXT=$(gpd --raw validate command-context progress \"$ARGUMENTS\")"
        )


def test_progress_prompt_requires_project_not_roadmap() -> None:
    command = (REPO_ROOT / "src/gpd/commands/progress.md").read_text(encoding="utf-8")

    assert 'files: ["GPD/PROJECT.md"]' in command
    assert 'files: ["GPD/ROADMAP.md"]' not in command


def test_new_milestone_prompt_mentions_planning_commit_docs() -> None:
    command = (REPO_ROOT / "src/gpd/commands/new-milestone.md").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / "src/gpd/specs/workflows/new-milestone.md").read_text(encoding="utf-8")

    for content in (command, workflow):
        assert "planning.commit_docs" in content
        assert "/gpd:discuss-phase [N]" in content or "/gpd:discuss-phase 1" in content


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
    assert "gpd state advance" in schema
    assert "gpd state advance-plan" not in schema
    assert "Preferred write path: `gpd state set-project-contract <path-to-contract.json>`." not in schema


def test_compare_branches_prompt_keeps_branch_summary_extraction_in_memory() -> None:
    workflow = (REPO_ROOT / "src/gpd/specs/workflows/compare-branches.md").read_text(encoding="utf-8")

    assert "Prefer parsing the `git show` output directly in memory." in workflow
    assert "do not write it to `GPD/tmp/` just to run a path-based extractor." in workflow
    assert "Keep branch-summary extraction in memory/stdout only" in workflow
    assert "do not use `GPD/tmp/`, `/tmp`, or another temp root for this step." in workflow


def test_help_prompts_surface_tangent_command_for_side_investigations() -> None:
    help_command = (COMMANDS_DIR / "help.md").read_text(encoding="utf-8")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    for content in (help_command, help_workflow):
        assert "/gpd:tangent" in content
        assert re.search(r"/gpd:tangent[^\n]*?(?:tangent|side investigation|alternative direction|parallel)", content, re.I)


def test_settings_and_research_mode_docs_keep_tangent_branch_taxonomy_strict() -> None:
    settings = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")
    new_project = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")
    research_modes = (
        REPO_ROOT / "src/gpd/specs/references/research/research-modes.md"
    ).read_text(encoding="utf-8")

    assert "Which starting workflow preset should GPD use for `GPD/config.json`?" in new_project
    assert "offer a preset choice before individual questions" in new_project
    assert "preview the resolved knobs before writing `GPD/config.json`" in new_project
    assert '"Core research (Recommended)"' in new_project
    assert '"Theory"' in new_project
    assert '"Numerics"' in new_project
    assert '"Publication / manuscript"' in new_project
    assert '"Full research"' in new_project
    assert "multiple hypothesis branches" not in settings
    assert "Minimal branching, fast convergence." not in settings
    assert "auto-switch to exploit once approach is validated" not in settings
    assert "does **not** by itself authorize git-backed hypothesis branches" in settings
    assert "surface tangent decisions explicitly" in settings
    assert "Suppress optional tangents unless the user explicitly requests them" in settings
    assert "Preset application must be explicit and previewable." in settings
    assert "Present the resolved bundle first, let the user preview it, then ask for an explicit apply/adjust choice." in settings
    assert "do **not** silently create git-backed hypothesis branches" in research_modes
    assert "only explicit tangent decisions become hypothesis branches or parallel plans" in research_modes
    assert "Flag complementary approaches as tangent candidates for optional parallel investigation" in research_modes


def test_regression_check_prompt_examples_include_optional_phase_before_quick_flag() -> None:
    verifier = (REPO_ROOT / "src/gpd/agents/gpd-verifier.md").read_text(encoding="utf-8")
    infra = (REPO_ROOT / "src/gpd/specs/references/orchestration/agent-infrastructure.md").read_text(encoding="utf-8")

    for content in (verifier, infra):
        assert "gpd regression-check [phase] [--quick]" in content
        assert "gpd regression-check [--quick]" not in content


def test_verifier_prompt_does_not_claim_regression_check_spawns_verifier() -> None:
    verifier = (REPO_ROOT / "src/gpd/agents/gpd-verifier.md").read_text(encoding="utf-8")

    assert "The regression-check command" not in verifier


def test_help_prompt_workflow_modes_match_current_settings_vocabulary() -> None:
    help_command = (COMMANDS_DIR / "help.md").read_text(encoding="utf-8")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    for content in (help_command, help_workflow):
        assert "Interactive Mode" not in content
        assert "YOLO Mode" not in content
        assert "Change anytime by editing `GPD/config.json`" not in content
        assert "Supervised" in content
        assert "Max quality" in content
        assert "Balanced" in content
        assert "Budget-aware" in content
        assert "runtime defaults" in content
        assert "tier-1" in content
        assert "tier-2" in content
        assert "tier-3" in content
        assert "YOLO" in content
        assert "/gpd:settings" in content
        assert "/gpd:discuss-phase" in content
        assert "execution.review_cadence" in content
        assert "planning.commit_docs" in content
        assert "git.branching_strategy" in content
        assert "gpd observe execution" in content
        assert "gpd cost" in content


def test_help_prompt_surfaces_workflow_presets_on_the_local_cli_surface() -> None:
    help_command = (COMMANDS_DIR / "help.md").read_text(encoding="utf-8")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    for content in (help_command, help_workflow):
        assert "**Workflow presets**" in content
        assert "Paper/manuscript workflows" in content
        assert "gpd doctor --runtime <runtime> --local|--global" in content
        assert "gpd presets list" in content
        assert "gpd presets show <preset>" in content
        assert "gpd presets apply <preset>" in content
        assert "not stored as a separate preset block" in content
        assert "failed preset rows degrade that workflow rather than blocking the base install" in content
        assert "/gpd:settings" in content
        assert "/gpd:set-profile" in content


def test_help_prompt_keeps_cost_surface_on_local_cli_not_runtime_slash_command() -> None:
    help_command = (COMMANDS_DIR / "help.md").read_text(encoding="utf-8")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    for content in (help_command, help_workflow):
        assert "gpd cost" in content
        assert "/gpd:cost" not in content
        assert "machine-local usage / cost summary" in content
        assert "recorded local telemetry" in content
        assert "not live budget enforcement or provider billing truth" in content


def test_help_prompt_session_management_keeps_pause_before_leave_and_resume_on_return() -> None:
    help_command = (COMMANDS_DIR / "help.md").read_text(encoding="utf-8")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    for content in (help_command, help_workflow):
        assert "**`/gpd:resume-work`**" in content
        assert "Uses resume files and project state to pick up where you left off" in content
        assert "Best first command when returning to paused or interrupted work" in content
        assert "gpd resume" in content
        assert "gpd resume --recent" in content
        assert "**`/gpd:pause-work`**" in content
        assert "Create context handoff when pausing work mid-phase." in content
        assert "Creates .continue-here file with current state" in content
        assert "Updates STATE.md session continuity section" in content
        assert "Captures in-progress work context" in content


def test_new_project_prompt_surfaces_discuss_phase_before_planning() -> None:
    command = (REPO_ROOT / "src/gpd/commands/new-project.md").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / "src/gpd/specs/workflows/new-project.md").read_text(encoding="utf-8")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    for content in (command, workflow, readme):
        assert "/gpd:discuss-phase 1" in content

    assert "Discuss phase 1 now?" in command
    assert "Discuss phase 1 now?" in workflow
    assert "Plan phase 1 now?" not in command
    assert "Plan phase 1 now?" not in workflow


def test_execute_phase_failure_recovery_counts_only_top_level_verification_statuses() -> None:
    workflow = (REPO_ROOT / "src/gpd/specs/workflows/execute-phase.md").read_text(encoding="utf-8")

    assert (
        "FAILED_COUNT=$(rg -c '^status: (gaps_found|expert_needed|human_needed)$'"
        in workflow
    )
    assert (
        "TOTAL_COUNT=$(rg -c '^status: (passed|gaps_found|expert_needed|human_needed)$'"
        in workflow
    )
    assert 'grep -c "status: failed"' not in workflow
    assert 'grep -c "status:"' not in workflow
