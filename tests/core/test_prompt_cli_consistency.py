"""Guardrails that keep prompt-authored CLI references aligned with the real CLI."""

from __future__ import annotations

import re
from pathlib import Path

from gpd.adapters.install_utils import expand_at_includes
from gpd.core import public_surface_contract as public_surface_contract_module
from gpd.core.cli_args import _ROOT_GLOBAL_FLAG_TOKENS
from gpd.core.public_surface_contract import (
    local_cli_bridge_note,
    local_cli_doctor_global_command,
    local_cli_doctor_local_command,
    local_cli_permissions_status_command,
    local_cli_plan_preflight_command,
    local_cli_resume_command,
    local_cli_resume_recent_command,
    local_cli_unattended_readiness_command,
    local_cli_validate_command_context_command,
    resume_authority_fields,
)
from gpd.registry import VALID_CONTEXT_MODES, _parse_frontmatter
from tests.doc_surface_contracts import (
    DOCTOR_RUNTIME_SCOPE_RE,
    assert_beginner_startup_routing_contract,
    assert_cost_advisory_contract,
    assert_cost_surface_discoverability,
    assert_health_command_public_contract,
    assert_help_command_all_extract_contract,
    assert_help_command_quick_start_extract_contract,
    assert_help_command_single_command_extract_contract,
    assert_help_workflow_command_index_contract,
    assert_help_workflow_quick_start_taxonomy_contract,
    assert_help_workflow_runtime_reference_contract,
    assert_recovery_ladder_contract,
    assert_resume_authority_contract,
    assert_runtime_reset_rediscovery_contract,
    assert_start_workflow_router_contract,
    assert_tour_command_surface_contract,
    assert_unattended_readiness_contract,
    assert_wolfram_plan_boundary_contract,
    assert_workflow_preset_surface_contract,
    resume_authority_public_vocabulary_intro,
    resume_compat_alias_fields,
)

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
    root_flag_pattern = "|".join(sorted((re.escape(flag) for flag in _ROOT_GLOBAL_FLAG_TOKENS), key=len, reverse=True))
    prefix_pattern = rf"(?:\s+(?:{root_flag_pattern}|--cwd(?:=[^\s`]+)?|--cwd\s+[^\s`]+))*"
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


def test_prompt_sources_keep_command_surface_rules_canonical_and_consistent() -> None:
    allowed = _declared_command_surfaces()
    cli_content = CLI_PATH.read_text(encoding="utf-8")
    root_commands = _declared_root_commands(cli_content)
    group_commands = _declared_groups(cli_content)

    invalid_surfaces: list[str] = []
    noncanonical_surfaces: list[str] = []
    raw_after_subcommand: list[str] = []
    summary_extract_fields: list[str] = []

    for path in _iter_prompt_sources():
        content = path.read_text(encoding="utf-8")
        relpath = str(path.relative_to(REPO_ROOT))

        for surface in _extract_gpd_command_surfaces(content, root_commands=root_commands, group_commands=group_commands):
            if surface not in allowed:
                invalid_surfaces.append(f"{relpath} -> {surface}")

        for match in NON_CANONICAL_GPD_COMMAND_RE.finditer(content):
            noncanonical_surfaces.append(f"{relpath} -> {match.group(0)}")

        for match in RAW_AFTER_SUBCOMMAND_RE.finditer(content):
            raw_after_subcommand.append(f"{relpath} -> {match.group(0)}")

        for match in SUMMARY_EXTRACT_FIELDS_RE.finditer(content):
            summary_extract_fields.append(f"{relpath} -> {match.group(0)}")

    assert invalid_surfaces == []
    assert noncanonical_surfaces == []
    assert raw_after_subcommand == []
    assert summary_extract_fields == []


def test_prompt_surface_extractor_matches_shared_root_global_flags() -> None:
    cli_content = CLI_PATH.read_text(encoding="utf-8")
    root_commands = _declared_root_commands(cli_content)
    group_commands = _declared_groups(cli_content)

    sample = """
    ```text
    gpd --version -v --cwd /tmp/workspace progress bar
    ```
    """

    assert _extract_gpd_command_surfaces(
        sample,
        root_commands=root_commands,
        group_commands=group_commands,
    ) == ["progress"]


def test_help_prompt_delegates_full_reference_to_workflow() -> None:
    help_prompt = (REPO_ROOT / "src/gpd/commands/help.md").read_text(encoding="utf-8")

    assert "@{GPD_INSTALL_DIR}/workflows/help.md" in help_prompt
    assert "workflow-owned help surface" in help_prompt
    assert "Compact Command Index (--all)" in help_prompt
    assert_help_command_all_extract_contract(help_prompt)
    assert_help_command_single_command_extract_contract(help_prompt)


def test_help_prompt_default_quick_start_extracts_workflow_owned_sections() -> None:
    help_prompt = (COMMANDS_DIR / "help.md").read_text(encoding="utf-8")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")
    quick_start = _extract_between(
        help_prompt,
        "## Step 2: Quick Start Extract (Default Output)",
        "## Step 3: Compact Command Index (--all)",
    )

    assert_help_command_quick_start_extract_contract(quick_start)
    assert_help_workflow_runtime_reference_contract(help_workflow)
    quick_start_reference = _extract_between(help_workflow, "## Quick Start", "## Command Index")
    command_index = _extract_between(help_workflow, "## Command Index", "## Detailed Command Reference")
    assert_help_workflow_quick_start_taxonomy_contract(quick_start_reference)
    assert_help_workflow_command_index_contract(command_index)
    assert_beginner_startup_routing_contract(quick_start_reference)
    assert "Usage: `/gpd:start`" not in quick_start_reference
    assert "## Detailed Command Reference" in help_workflow
    assert "gpd:new-project -> gpd:discuss-phase -> gpd:plan-phase -> gpd:execute-phase -> gpd:verify-work -> repeat" in help_workflow
    assert "gpd init new-project" not in help_workflow
    for token in ("gpd:discuss-phase", "gpd:write-paper", "gpd:tangent", "gpd:set-tier-models", "gpd:settings"):
        assert token in command_index


def test_help_prompt_keeps_workflow_preset_readiness_on_local_cli_surface() -> None:
    help_command = (COMMANDS_DIR / "help.md").read_text(encoding="utf-8")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")
    quick_start = _extract_between(
        help_command,
        "## Step 2: Quick Start Extract (Default Output)",
        "## Step 3: Compact Command Index (--all)",
    )

    assert "## Invocation Surfaces" not in quick_start
    assert "Include the workflow-owned `## Quick Start` section." in quick_start
    assert "Append this one wrapper-owned line" in quick_start
    assert_help_workflow_runtime_reference_contract(help_workflow)
    assert "executable probes" in help_workflow
    assert "pdflatex" in help_workflow
    assert "wolframscript" in help_workflow
    assert DOCTOR_RUNTIME_SCOPE_RE.search(help_workflow) is not None
    assert_wolfram_plan_boundary_contract(help_workflow)
    assert_workflow_preset_surface_contract(help_workflow)
    assert "Workflow preset tooling is layered on top of the base install; it does not change runtime permission alignment." in help_workflow


def test_start_prompt_delegates_routing_to_workflow_only() -> None:
    start_command = (COMMANDS_DIR / "start.md").read_text(encoding="utf-8")
    start_command_expanded = expand_at_includes(start_command, REPO_ROOT / "src/gpd", "/runtime/")
    start_workflow = (WORKFLOWS_DIR / "start.md").read_text(encoding="utf-8")

    assert "@{GPD_INSTALL_DIR}/workflows/start.md" in start_command
    assert "@{GPD_INSTALL_DIR}/references/onboarding/beginner-command-taxonomy.md" in start_command
    assert "actual first-run chooser when the user wants the right next action" in start_command_expanded
    assert "read-only walkthrough when the user wants orientation before choosing a path" in start_command_expanded
    assert "explain official terms the first time they appear" in start_command
    assert "gpd:tour" in start_command_expanded
    assert_start_workflow_router_contract(start_workflow)
    assert local_cli_resume_recent_command() in start_workflow
    assert "in your normal terminal to find the project first" in start_workflow
    assert "The recent-project picker is advisory; choose the workspace there" in start_workflow
    assert "reloads canonical state for that project." in start_workflow
    assert "GPD may auto-select it" in start_workflow
    assert "recent-project picker" in start_workflow
    assert "Then open that project folder in the runtime and run" in start_workflow
    assert "`gpd:resume-work`." in start_workflow
    assert "the in-runtime continuation step once the recovery ladder has identified the right project" in start_workflow
    assert "reopened its workspace" in start_workflow
    assert "Read `{GPD_INSTALL_DIR}/workflows/new-project.md` with the file-read tool." not in start_workflow
    assert "Read `{GPD_INSTALL_DIR}/workflows/help.md` with the file-read tool." not in start_workflow
    assert "Read `{GPD_INSTALL_DIR}/workflows/tour.md` with the file-read tool." not in start_workflow
    assert "{GPD_INSTALL_DIR}/commands/suggest-next.md" not in start_workflow


def test_tour_prompt_delegates_routing_to_workflow_only() -> None:
    tour_command = (COMMANDS_DIR / "tour.md").read_text(encoding="utf-8")
    tour_command_expanded = expand_at_includes(tour_command, REPO_ROOT / "src/gpd", "/runtime/")
    tour_workflow = (WORKFLOWS_DIR / "tour.md").read_text(encoding="utf-8")

    assert "@{GPD_INSTALL_DIR}/workflows/tour.md" in tour_command
    assert "@{GPD_INSTALL_DIR}/references/onboarding/beginner-command-taxonomy.md" in tour_command
    assert "teaching surface, not a chooser" in tour_command
    assert "safe beginner walkthrough of the core GPD command paths" in tour_command
    assert "gpd:set-tier-models" in tour_command
    assert "gpd:settings" in tour_command
    assert "gpd:start" in tour_command_expanded
    assert "gpd:resume-work" in tour_command_expanded
    assert_tour_command_surface_contract(tour_workflow)
    assert "$ARGUMENTS" in tour_workflow
    assert "Do not narrow the command list, select a path, or route based on it." in tour_workflow
    assert "the runtime, where you use the GPD command prefix provided for that runtime" in tour_workflow
    assert "Normal terminal vs runtime" in tour_workflow


def test_help_workflow_surfaces_start_as_first_run_router() -> None:
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")
    quick_start_reference = _extract_between(help_workflow, "## Quick Start", "## Command Index")

    assert "gpd:start" in help_workflow
    assert "Guided first-run router" in help_workflow
    assert "gpd:tour" in help_workflow
    assert "guided tour" in help_workflow.lower()
    assert_beginner_startup_routing_contract(quick_start_reference)


def test_prompt_docs_keep_wolfram_as_shared_capability_not_runtime_config_surface() -> None:
    help_command = (COMMANDS_DIR / "help.md").read_text(encoding="utf-8")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")
    settings_workflow = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")
    tooling_ref = (REPO_ROOT / "src/gpd/specs/references/tooling/tool-integration.md").read_text(encoding="utf-8")

    forbidden_tokens = (
        "gpd-wolfram",
        "gpd-mcp-wolfram",
        "GPD_WOLFRAM_MCP_API_KEY",
        "GPD_WOLFRAM_MCP_ENDPOINT",
        "WOLFRAM_MCP_SERVICE_API_KEY",
    )
    for content in (help_command, help_workflow, settings_workflow):
        for token in forbidden_tokens:
            assert token not in content

    assert "@{GPD_INSTALL_DIR}/workflows/help.md" in help_command
    assert_unattended_readiness_contract(help_workflow)
    assert_wolfram_plan_boundary_contract(help_workflow)
    assert "gpd integrations enable wolfram" in help_workflow
    assert "gpd integrations disable wolfram" in help_workflow
    assert_workflow_preset_surface_contract(help_workflow)

    assert "Mathematica / Wolfram Language" in tooling_ref
    assert "declare it as `tool: wolfram` in `tool_requirements`" in tooling_ref
    assert "gpd validate plan-preflight" in tooling_ref


def test_suggest_next_prompt_uses_real_cli_subcommand() -> None:
    suggest_prompt = (REPO_ROOT / "src/gpd/commands/suggest-next.md").read_text(encoding="utf-8")

    assert_runtime_reset_rediscovery_contract(suggest_prompt)
    assert "Uses `gpd --raw suggest`" in suggest_prompt
    assert "Local CLI fallback: `gpd --raw suggest`" in suggest_prompt
    assert (
        f"If you still need to rediscover the project first, do that in your normal terminal with `{local_cli_resume_command()}` for the current workspace or `{local_cli_resume_recent_command()}` for the explicit multi-project picker before reopening the runtime."
        in suggest_prompt
    )
    assert "Keep `/clear` as a fresh-context reset, not as a recovery step." in suggest_prompt
    assert "`/clear` first -> fresh context window, then `{command}`." in suggest_prompt
    assert (
        f"If you still need to rediscover the project first, do that in your normal terminal with `{local_cli_resume_command()}` for the current workspace or `{local_cli_resume_recent_command()}` for a different project before reopening the runtime."
        in suggest_prompt
    )
    assert (
        f"`/clear` first -> fresh context window, then `{{command}}`; if you still need to rediscover the project, use `{local_cli_resume_recent_command()}` before reopening the runtime"
        not in suggest_prompt
    )
    assert "gpd suggest-next to scan" not in suggest_prompt


def test_tangent_prompt_routes_into_existing_workflows() -> None:
    tangent_command = (COMMANDS_DIR / "tangent.md").read_text(encoding="utf-8")
    tangent_workflow = (WORKFLOWS_DIR / "tangent.md").read_text(encoding="utf-8")

    assert "name: gpd:tangent" in tangent_command
    assert "@{GPD_INSTALL_DIR}/workflows/tangent.md" in tangent_command
    assert "gpd:quick" in tangent_command
    assert "gpd:add-todo" in tangent_command
    assert "gpd:branch-hypothesis" in tangent_command

    for token in (
        "Stay on the main path",
        "Run a bounded quick check now",
        "Capture and defer",
        "Open a hypothesis branch",
        "live execution review stop surfaces a tangent proposal",
        "{GPD_INSTALL_DIR}/workflows/quick.md",
        "{GPD_INSTALL_DIR}/workflows/add-todo.md",
        "{GPD_INSTALL_DIR}/workflows/branch-hypothesis.md",
    ):
        assert token in tangent_workflow


def test_progress_prompt_runs_preflight_after_init_context() -> None:
    command = (REPO_ROOT / "src/gpd/commands/progress.md").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / "src/gpd/specs/workflows/progress.md").read_text(encoding="utf-8")

    assert "@{GPD_INSTALL_DIR}/workflows/progress.md" in command
    assert "Read `{GPD_INSTALL_DIR}/workflows/progress.md` with the file-read tool and follow it exactly." in command
    assert "INIT=$(gpd --raw init progress --include state,roadmap,project,config)" not in command
    assert "CONTEXT=$(gpd --raw validate command-context progress \"$ARGUMENTS\")" not in command
    assert "The recent-project picker is advisory" not in command
    assert "reloads canonical state for that project" not in command

    assert "INIT=$(gpd --raw init progress --include state,roadmap,project,config)" in workflow
    assert "CONTEXT=$(gpd --raw validate command-context progress \"$ARGUMENTS\")" in workflow
    assert workflow.index("INIT=$(gpd --raw init progress --include state,roadmap,project,config)") < workflow.index(
        "CONTEXT=$(gpd --raw validate command-context progress \"$ARGUMENTS\")"
    )


def test_health_prompt_documents_the_real_raw_health_report_shape() -> None:
    health_command = (COMMANDS_DIR / "health.md").read_text(encoding="utf-8")

    assert_health_command_public_contract(health_command)


def test_progress_prompt_requires_project_not_roadmap() -> None:
    command = (REPO_ROOT / "src/gpd/commands/progress.md").read_text(encoding="utf-8")

    assert 'files: ["GPD/PROJECT.md"]' in command
    assert 'files: ["GPD/ROADMAP.md"]' not in command


def test_progress_prompt_and_help_clarify_runtime_vs_local_cli_boundary() -> None:
    command = (REPO_ROOT / "src/gpd/commands/progress.md").read_text(encoding="utf-8")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")
    progress_section = _extract_between(help_workflow, "### Progress Tracking", "### Session Management")
    normalized_command = " ".join(command.split())
    normalized_progress_section = " ".join(progress_section.split())

    assert "The local CLI `gpd progress` is a separate read-only renderer" in normalized_command
    assert "takes `json|bar|table` and does not accept these flags" in normalized_command
    assert "The local CLI `gpd progress` is a separate read-only renderer" in normalized_progress_section
    assert "Local CLI: `gpd progress json|bar|table`" in normalized_progress_section


def test_plan_phase_prompt_is_a_thin_dispatch_shell() -> None:
    command = (REPO_ROOT / "src/gpd/commands/plan-phase.md").read_text(encoding="utf-8")

    assert "@{GPD_INSTALL_DIR}/workflows/plan-phase.md" in command
    assert "@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md" not in command
    assert "@{GPD_INSTALL_DIR}/references/ui/ui-brand.md" not in command
    assert "Follow the included workflow file exactly." in command
    assert "agent: gpd-planner" in command
    assert "What Makes a Good Physics Plan" not in command
    assert "Common Failure Modes" not in command
    assert "Quick Checklist Before Approving a Plan" not in command
    assert "Domain-Aware Planning" not in command
    assert "gpd --raw init plan-phase" not in command


def test_new_milestone_prompt_mentions_planning_commit_docs() -> None:
    command = (REPO_ROOT / "src/gpd/commands/new-milestone.md").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / "src/gpd/specs/workflows/new-milestone.md").read_text(encoding="utf-8")

    for content in (command, workflow):
        assert "planning.commit_docs" in content
        assert "gpd:discuss-phase [N]" in content or "gpd:discuss-phase 1" in content


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


def test_new_project_prompt_uses_stdin_for_contract_validation_and_persistence() -> None:
    workflow = (REPO_ROOT / "src/gpd/specs/workflows/new-project.md").read_text(encoding="utf-8")

    assert 'printf \'%s\\n\' "$PROJECT_CONTRACT_JSON" | gpd --raw validate project-contract - --mode approved' in workflow
    assert 'printf \'%s\\n\' "$PROJECT_CONTRACT_JSON" | gpd state set-project-contract -' in workflow
    assert "gpd permissions sync --runtime <runtime>" in workflow
    assert "gpd permissions sync --runtime <name>" not in workflow
    assert "/tmp/gpd-project-contract.json" not in workflow
    assert "temporary JSON file if needed" not in workflow


def test_state_json_schema_stays_aligned_with_stdin_contract_persistence_flow() -> None:
    schema = (REPO_ROOT / "src/gpd/specs/templates/state-json-schema.md").read_text(encoding="utf-8")

    assert 'printf \'%s\\n\' "$PROJECT_CONTRACT_JSON" | gpd --raw validate project-contract -' in schema
    assert 'printf \'%s\\n\' "$PROJECT_CONTRACT_JSON" | gpd state set-project-contract -' in schema
    assert "gpd state advance" in schema
    assert "gpd state advance-plan" not in schema
    assert "Preferred write path: `gpd state set-project-contract <path-to-contract.json>`." not in schema


def test_new_project_and_state_schema_surface_contract_id_integrity_rules() -> None:
    workflow = (REPO_ROOT / "src/gpd/specs/workflows/new-project.md").read_text(encoding="utf-8")
    schema = expand_at_includes(
        (REPO_ROOT / "src/gpd/specs/templates/state-json-schema.md").read_text(encoding="utf-8"),
        REPO_ROOT / "src/gpd/specs",
        "/runtime/",
    )

    assert "do not paraphrase the schema here; reuse its exact keys, enum values, list/object shapes, ID-linkage rules, and proof-bearing claim requirements" in workflow
    assert "Same-kind IDs must be unique within each section." in schema
    assert "must not match any declared contract ID" in schema


def test_compare_branches_prompt_keeps_branch_summary_extraction_in_memory() -> None:
    workflow = (REPO_ROOT / "src/gpd/specs/workflows/compare-branches.md").read_text(encoding="utf-8")

    assert "Prefer parsing the `git show` output directly in memory." in workflow
    assert "do not write it to `GPD/tmp/` just to run a path-based extractor." in workflow
    assert "Keep branch-summary extraction in memory/stdout only" in workflow
    assert "do not use `GPD/tmp/`, `/tmp`, or another temp root for this step." in workflow


def test_help_prompts_surface_tangent_command_for_side_investigations() -> None:
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    assert "gpd:tangent" in help_workflow
    assert re.search(r"gpd:tangent[^\n]*?(?:tangent|side investigation|alternative direction|parallel)", help_workflow, re.I)


def test_settings_and_research_mode_docs_keep_tangent_branch_taxonomy_strict() -> None:
    settings = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")
    new_project = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")
    research_modes = (
        REPO_ROOT / "src/gpd/specs/references/research/research-modes.md"
    ).read_text(encoding="utf-8")

    assert "Which starting workflow preset should GPD use for `GPD/config.json`?" in new_project
    assert "offer a preset choice before individual questions" in new_project
    assert "preset bundle over the existing config knobs" in new_project
    assert "preview" in new_project
    assert "writing `GPD/config.json`" in new_project
    assert "Do not persist a separate preset key." in new_project
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
    assert "preview" in settings
    assert "explicit apply or customize choice" in settings
    assert "do **not** silently create git-backed hypothesis branches" in research_modes
    assert "only explicit tangent decisions become hypothesis branches or parallel plans" in research_modes
    assert "Flag complementary approaches as tangent candidates for optional parallel investigation" in research_modes


def test_regression_check_prompt_examples_include_optional_phase_before_quick_flag() -> None:
    verifier_raw = (REPO_ROOT / "src/gpd/agents/gpd-verifier.md").read_text(encoding="utf-8")
    infra = (REPO_ROOT / "src/gpd/specs/references/orchestration/agent-infrastructure.md").read_text(encoding="utf-8")

    assert "references/orchestration/agent-infrastructure.md" in verifier_raw
    assert "@{GPD_INSTALL_DIR}/references/orchestration/agent-infrastructure.md" not in verifier_raw
    assert "<!-- [included:" not in verifier_raw
    assert "gpd regression-check [phase] [--quick]" in infra
    assert "gpd regression-check [--quick]" not in infra


def test_verifier_prompt_does_not_claim_regression_check_spawns_verifier() -> None:
    verifier = (REPO_ROOT / "src/gpd/agents/gpd-verifier.md").read_text(encoding="utf-8")

    assert "The regression-check command" not in verifier


def test_help_prompt_workflow_modes_match_current_settings_vocabulary() -> None:
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    assert "Interactive Mode" not in help_workflow
    assert "YOLO Mode" not in help_workflow
    assert "Change anytime by editing `GPD/config.json`" not in help_workflow
    assert "Supervised" in help_workflow
    assert "Max quality" in help_workflow
    assert "Balanced" in help_workflow
    assert "Budget-aware" in help_workflow
    assert "runtime defaults" in help_workflow
    assert "tier-1" in help_workflow
    assert "tier-2" in help_workflow
    assert "tier-3" in help_workflow
    assert "YOLO" in help_workflow
    assert "gpd:set-tier-models" in help_workflow
    assert "gpd:settings" in help_workflow
    assert "gpd:discuss-phase" in help_workflow
    assert "execution.review_cadence" in help_workflow
    assert "planning.commit_docs" in help_workflow
    assert "git.branching_strategy" in help_workflow
    assert "gpd observe execution" in help_workflow
    assert_cost_surface_discoverability(help_workflow)


def test_help_prompt_surfaces_workflow_presets_on_the_local_cli_surface() -> None:
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    assert "### Optional Local CLI Add-Ons" in help_workflow
    assert "**Workflow presets**" in help_workflow
    assert "Paper/manuscript workflows" in help_workflow
    assert DOCTOR_RUNTIME_SCOPE_RE.search(help_workflow) is not None
    assert "executable probes" in help_workflow
    assert_workflow_preset_surface_contract(help_workflow)
    assert "paper-toolchain readiness" in help_workflow
    assert "degrade `write-paper`" in help_workflow
    assert "`paper-build` remains the build contract" in help_workflow
    assert "`arxiv-submission` requires the built manuscript" in help_workflow
    assert "gpd:set-tier-models" in help_workflow
    assert "gpd:settings" in help_workflow
    assert "gpd:set-profile" in help_workflow


def test_help_prompt_keeps_cost_surface_on_local_cli_not_runtime_slash_command() -> None:
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    assert "gpd cost" in help_workflow
    assert "/gpd:cost" not in help_workflow
    assert_cost_advisory_contract(help_workflow)


def test_prompt_and_public_surface_contract_agree_on_runtime_readiness_and_plan_validation_surfaces() -> None:
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")
    bridge_note = local_cli_bridge_note()

    assert local_cli_unattended_readiness_command() in help_workflow
    assert local_cli_permissions_status_command() in help_workflow
    assert local_cli_plan_preflight_command() in help_workflow
    assert local_cli_doctor_local_command() in help_workflow
    assert local_cli_doctor_global_command() in help_workflow
    assert local_cli_validate_command_context_command() in help_workflow
    assert public_surface_contract_module.local_cli_bridge_purpose_phrase() in bridge_note


def test_help_workflow_mentions_all_authoritative_local_cli_bridge_commands() -> None:
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")
    for command in public_surface_contract_module.load_public_surface_contract().local_cli_bridge.named_commands.ordered():
        assert command in help_workflow

    assert local_cli_doctor_local_command() in help_workflow
    assert local_cli_doctor_global_command() in help_workflow
    assert local_cli_validate_command_context_command() in help_workflow


def test_help_prompt_session_management_keeps_pause_before_leave_and_resume_on_return() -> None:
    help_workflow = expand_at_includes(
        (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8"),
        REPO_ROOT / "src/gpd",
        "/runtime/",
    )

    assert_runtime_reset_rediscovery_contract(
        help_workflow,
        extra_reset_fragments=(f"then run {local_cli_resume_command()} in your normal terminal",),
        extra_reset_not_recovery_fragments=(f"then run {local_cli_resume_command()} in your normal terminal",),
    )
    assert "**`gpd:resume-work`**" in help_workflow
    assert "**`gpd:pause-work`**" in help_workflow
    assert_resume_authority_contract(
        help_workflow,
        allow_explicit_alias_examples=False,
        require_generic_compatibility_note=True,
    )
    assert resume_authority_public_vocabulary_intro() in help_workflow
    assert "compatibility-only intake fields stay internal" in help_workflow.lower()
    assert "state.json.continuation.handoff.resume_file" not in help_workflow
    assert "compat_resume_surface" not in help_workflow
    assert resume_authority_fields() == (
        "active_resume_kind",
        "active_resume_origin",
        "active_resume_pointer",
        "active_bounded_segment",
        "derived_execution_head",
        "active_resume_result",
        "continuity_handoff_file",
        "recorded_continuity_handoff_file",
        "missing_continuity_handoff_file",
        "resume_candidates",
    )
    assert not any(alias in resume_authority_fields() for alias in resume_compat_alias_fields())
    assert_recovery_ladder_contract(
        help_workflow,
        resume_work_fragments=("gpd:resume-work", "/gpd:resume-work"),
        suggest_next_fragments=("gpd:suggest-next", "/gpd:suggest-next"),
        pause_work_fragments=("gpd:pause-work", "/gpd:pause-work"),
    )


def test_new_project_prompt_surfaces_discuss_phase_before_planning_in_command_and_workflow() -> None:
    command = (REPO_ROOT / "src/gpd/commands/new-project.md").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / "src/gpd/specs/workflows/new-project.md").read_text(encoding="utf-8")

    for content in (command, workflow):
        assert "gpd:discuss-phase 1" in content

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
